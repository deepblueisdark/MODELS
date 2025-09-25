#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plota a malha MPAS (arestas) em três projeções:
 - Globo (Ortográfica centrada em lon=-50, lat=-25)
 - Plano (Plate Carrée global)
 - Zoom (extensão configurável por CLI)

Exemplos:
  python plota_mesh.py 'x1;292829.nc'
  python plota_mesh.py 'x1;292829.nc' malha_
  python plota_mesh.py 'x1;292829.nc' --prefix malha_ --lon-min 280 --lon-max 330 --lat-min -50 --lat-max 10 -lw 0.4
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import cartopy.crs as ccrs
import cartopy.feature as cfeature


# ------------------------- utilidades ------------------------- #
def _normalize_lon(lon: float) -> float:
    """Aceita 0–360 ou -180–180 e normaliza para [-180, 180)."""
    return ((lon + 180.0) % 360.0) - 180.0


def _open_dataset_with_fallback(path_nc: str, decode_cf: bool = False):
    """Tenta abrir via netcdf4 → h5netcdf → scipy."""
    last_err = None
    for engine in ("netcdf4", "h5netcdf", "scipy"):
        try:
            return xr.open_dataset(path_nc, engine=engine, decode_cf=decode_cf)
        except Exception as e:
            last_err = e
    raise RuntimeError(
        "Não consegui abrir o NetCDF com nenhum engine. "
        "Instale 'netCDF4' ou 'h5netcdf' ou 'scipy'."
    ) from last_err


# ------------------------- leitura do grid ------------------------- #
def read_mpas_grid(path_nc: str):
    """
    Lê lon/lat dos vértices e conectividade das arestas (verticesOnEdge),
    monta segmentos [(lon0,lat0)→(lon1,lat1)] já corrigindo antimeridiano.

    Retorna:
        segments : np.ndarray shape (nEdges, 2, 2) em graus
    """
    ds = _open_dataset_with_fallback(path_nc, decode_cf=False)

    # MPAS normalmente guarda em radianos
    lonVertex = np.degrees(ds["lonVertex"].values).astype(np.float64)  # (nVertices,)
    latVertex = np.degrees(ds["latVertex"].values).astype(np.float64)  # (nVertices,)

    verticesOnEdge = ds["verticesOnEdge"].values.astype(np.int64) - 1  # 1-based → 0-based
    if verticesOnEdge.ndim != 2 or verticesOnEdge.shape[1] != 2:
        raise ValueError(f"verticesOnEdge shape inválido: {verticesOnEdge.shape} (esperado: nEdges x 2)")

    v0 = verticesOnEdge[:, 0]
    v1 = verticesOnEdge[:, 1]

    lons0 = lonVertex[v0]
    lats0 = latVertex[v0]
    lons1 = lonVertex[v1]
    lats1 = latVertex[v1]

    # Corrige cruzamento do antimeridiano (diferença > 180°)
    diff = np.abs(lons0 - lons1)
    mask = diff > 180.0
    # traz o maior para o intervalo [-360, 0) quando cruza
    adjust0 = (lons0 > lons1) & mask
    adjust1 = (lons1 > lons0) & mask
    lons0 = lons0.copy()
    lons1 = lons1.copy()
    lons0[adjust0] -= 360.0
    lons1[adjust1] -= 360.0

    segments = np.stack(
        [np.stack([lons0, lats0], axis=1), np.stack([lons1, lats1], axis=1)],
        axis=1,
    )

    ds.close()
    return segments


# ------------------------- desenho ------------------------- #
def add_base_features(ax, coastline_res: str = "50m"):
    ax.coastlines(resolution=coastline_res, linewidth=0.6)
    ax.add_feature(cfeature.BORDERS, linewidth=0.2)


def draw_segments(ax, segments, lw: float = 0.3):
    lc = LineCollection(
        segments,
        linewidths=lw,
        zorder=5,
        transform=ccrs.PlateCarree(),  # dados em (lon, lat) graus
    )
    ax.add_collection(lc)


def plot_globe(segments, out_png: str, linewidth: float):
    proj = ccrs.Orthographic(central_longitude=-50.0, central_latitude=-25.0)
    fig = plt.figure(figsize=(10, 10))
    ax = plt.axes(projection=proj)
    ax.set_global()
    add_base_features(ax)
    draw_segments(ax, segments, lw=linewidth)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_planar(segments, out_png: str, linewidth: float):
    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(12, 6))
    ax = plt.axes(projection=proj)
    ax.set_global()
    add_base_features(ax)
    draw_segments(ax, segments, lw=linewidth)
    ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_zoom(segments, out_png: str, linewidth: float,
              lon_min: float, lon_max: float, lat_min: float, lat_max: float):
    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(8, 8))
    ax = plt.axes(projection=proj)
    add_base_features(ax)
    draw_segments(ax, segments, lw=linewidth)
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)


# ------------------------- CLI ------------------------- #
def parse_args():
    p = argparse.ArgumentParser(
        description="Plota malha MPAS (arestas) em globo, plano e zoom."
    )
    # Compat: ainda aceita --input/-i
    p.add_argument("--input", "-i", default=None, help="Arquivo MPAS grid (ex.: grid.nc)")
    # Posicional principal (arquivo)
    p.add_argument("input_pos", nargs="?", default=None, help="Arquivo MPAS grid (ex.: grid.nc)")
    # Prefixo (flag ou 2º posicional)
    p.add_argument("--prefix", "-p", default=None,
                   help="Prefixo dos PNGs. Se omitido, usa <stem do arquivo>_ .")
    p.add_argument("prefix_pos", nargs="?", default=None,
                   help="Prefixo dos PNGs (opcional).")

    # Espessura das linhas
    p.add_argument("--linewidth", "-lw", type=float, default=0.3,
                   help="Espessura das linhas das arestas (default: 0.3).")

    # Limites do zoom (defaults pedidos)
    p.add_argument("--lon-min", type=float, default=-80.0,
                   help="Longitude mínima do zoom (aceita 0–360 ou -180–180). Default: -80")
    p.add_argument("--lon-max", type=float, default=-30.0,
                   help="Longitude máxima do zoom (aceita 0–360 ou -180–180). Default: -30")
    p.add_argument("--lat-min", type=float, default=-50.0,
                   help="Latitude mínima do zoom. Default: -50")
    p.add_argument("--lat-max", type=float, default=10.0,
                   help="Latitude máxima do zoom. Default: 10")

    return p.parse_args()


def main():
    args = parse_args()

    # arquivo: flag > posicional > "grid.nc"
    path_nc = args.input or args.input_pos or "grid.nc"
    path_nc = Path(path_nc)
    if not path_nc.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path_nc}")

    # prefixo: flag > posicional > <stem>_
    prefix = args.prefix or args.prefix_pos or (path_nc.stem + "_")

    # normaliza longitudes do zoom (aceita 0–360 ou -180–180)
    lon_min = _normalize_lon(args.lon_min)
    lon_max = _normalize_lon(args.lon_max)
    lat_min = args.lat_min
    lat_max = args.lat_max

    # leitura e plotagem
    segments = read_mpas_grid(str(path_nc))
    lw = args.linewidth

    plot_globe(segments, f"{prefix}globo.png", lw)
    plot_planar(segments, f"{prefix}plano.png", lw)
    plot_zoom(segments, f"{prefix}zoom.png", lw, lon_min, lon_max, lat_min, lat_max)

    print(
        "Figuras salvas:\n  "
        f"{prefix}globo.png\n  {prefix}plano.png\n  {prefix}zoom.png\n"
        f"Zoom: lon=({lon_min:.3f},{lon_max:.3f}), lat=({lat_min:.3f},{lat_max:.3f})"
    )


if __name__ == "__main__":
    main()
