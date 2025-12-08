#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_terrain.py — MPAS terrain no estilo do tutorial (painel: plano + globo)

- Triangulação: usa cellsOnVertex (triângulos) e lonCell/latCell (pontos)
- Plano (Plate Carrée) e Ortho (Orthographic) no mesmo PNG
- Colorbar com extend, grades e rótulos, oceano/terra/bordas
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.colors import BoundaryNorm, Normalize
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER


# ---------------- utilidades ---------------- #
def _normalize_lon(x):
    """Aceita escalar/array em 0–360 ou -180–180 e normaliza p/ [-180,180)."""
    return ((np.asarray(x, dtype=float) + 180.0) % 360.0) - 180.0


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


def _compute_extent_from_points(lon_deg, lat_deg, pad_frac=0.01):
    lon_min = float(np.min(lon_deg)); lon_max = float(np.max(lon_deg))
    lat_min = float(np.min(lat_deg)); lat_max = float(np.max(lat_deg))
    dx = (lon_max - lon_min) * pad_frac
    dy = (lat_max - lat_min) * pad_frac
    return lon_min - dx, lon_max + dx, lat_min - dy, lat_max + dy


# -------------- leitura + triangulação -------------- #
def load_triangulation(path_nc: str, varname: str):
    """
    Lê lon/lat dos centros de célula, cellsOnVertex e a variável.
    Retorna:
      tri (matplotlib.tri.Triangulation), values (nCells,), lon, lat
    """
    ds = _open_dataset_with_fallback(path_nc, decode_cf=False)

    lonCell = np.degrees(ds["lonCell"].values).astype(np.float64)
    latCell = np.degrees(ds["latCell"].values).astype(np.float64)
    lonCell = _normalize_lon(lonCell)

    if "cellsOnVertex" not in ds:
        raise KeyError("Arquivo não contém 'cellsOnVertex' (necessário p/ triangulação).")
    # (nVertices, 3), 1-based -> 0-based
    triangles = ds["cellsOnVertex"].values.astype(np.int64) - 1
    if triangles.shape[1] != 3:
        raise ValueError(f"cellsOnVertex tem {triangles.shape[1]} colunas; esperado 3.")

    # variável (ex.: 'ter') → reduzir p/ (nCells,)
    if varname not in ds.variables:
        raise KeyError(f"Variável '{varname}' não encontrada.")
    var = ds[varname].values
    nCells = lonCell.shape[0]

    if var.ndim == 1 and var.shape[0] == nCells:
        values = var.astype(np.float64)
    else:
        # heurísticas comuns: (nCells,1), (time,nCells), (nCells,level)...
        axis = None
        for i, s in enumerate(var.shape):
            if s == nCells:
                axis = i; break
        if axis is None:
            raise ValueError(f"Dimensões inesperadas para '{varname}': {var.shape}")
        index = [0]*var.ndim
        index[axis] = slice(None)
        values = var[tuple(index)].astype(np.float64)

    # Triangulação
    tri = mtri.Triangulation(lonCell, latCell, triangles=triangles)

    # Mascara triângulos que cruzam o antimeridiano (evita “faixas” atravessando 180º)
    tri_lon = lonCell[tri.triangles]
    cross = (np.ptp(tri_lon, axis=1) > 180.0)
    if tri.mask is None:
        tri.set_mask(cross)
    else:
        tri.set_mask(tri.mask | cross)

    ds.close()
    return tri, values, lonCell, latCell


# ---------------- aparência/cartopy ---------------- #
def add_common_features(ax, coast_res="50m", add_states=False, add_lakes=False):
    ax.add_feature(cfeature.OCEAN, zorder=0)   # oceano “abaixo”
    ax.add_feature(cfeature.LAND, zorder=0)
    ax.coastlines(resolution=coast_res, linewidth=0.6)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4)
    if add_states:
        states = cfeature.NaturalEarthFeature(
            "cultural", "admin_1_states_provinces_lines", coast_res,
            edgecolor="k", facecolor="none")
        ax.add_feature(states, linewidth=0.3)
    if add_lakes:
        ax.add_feature(cfeature.LAKES, edgecolor="k", facecolor="none", linewidth=0.3)


def add_gridlines(ax, xlocs=None, ylocs=None, labelsize=8):
    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="k", alpha=0.25, linestyle="-")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": labelsize}
    gl.ylabel_style = {"size": labelsize}
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    if xlocs is not None:
        gl.xlocator = xlocs
    if ylocs is not None:
        gl.ylocator = ylocs
    return gl


# ---------------- plotters ---------------- #
def plot_plate(ax, tri, values, levels, vmin, vmax, cmap):
    cs = ax.tricontourf(
        tri, values,
        levels=levels if levels is not None else 16,
        cmap=cmap,
        vmin=None if levels is not None else vmin,
        vmax=None if levels is not None else vmax,
        extend="both",
        transform=ccrs.PlateCarree(),
    )
    return cs


def plot_ortho(ax, tri, values, levels, vmin, vmax, cmap):
    ax.set_global()
    cs = ax.tricontourf(
        tri, values,
        levels=levels if levels is not None else 16,
        cmap=cmap,
        vmin=None if levels is not None else vmin,
        vmax=None if levels is not None else vmax,
        extend="both",
        transform=ccrs.PlateCarree(),
    )
    return cs


# ---------------- CLI ---------------- #
def parse_args():
    p = argparse.ArgumentParser(
        description="Plota terreno MPAS em painel (plano + globo) no estilo do tutorial."
    )
    p.add_argument("input", help="Arquivo MPAS init/grid (ex.: init.nc)")
    p.add_argument("--prefix", "-p", default=None,
                   help="Prefixo de saída (default: <stem>_)")
    p.add_argument("--var", default="ter", help="Variável (default: ter)")
    p.add_argument("--cmap", default="terrain", help="Colormap (default: terrain)")

    # níveis explícitos OU automáticos
    p.add_argument("--levels", default=None,
                   help="Níveis explícitos, separados por vírgula (ex.: 0,250,500,...).")
    p.add_argument("--nlevels", type=int, default=24,
                   help="Nº de níveis quando níveis explícitos NÃO forem dados (default: 24).")
    p.add_argument("--vmin", type=float, default=None, help="Mínimo (quando sem --levels).")
    p.add_argument("--vmax", type=float, default=None, help="Máximo (quando sem --levels).")

    # extent do PLANO
    p.add_argument("--extent-mode", choices=["global", "data", "cli"], default="global",
                   help="Como definir o extent do PLANO (default: global).")
    p.add_argument("--lon-min", type=float, default=-80.0, help="Para extent 'cli'.")
    p.add_argument("--lon-max", type=float, default=-30.0, help="Para extent 'cli'.")
    p.add_argument("--lat-min", type=float, default=-50.0, help="Para extent 'cli'.")
    p.add_argument("--lat-max", type=float, default=10.0, help="Para extent 'cli'.")
    p.add_argument("--pad-frac", type=float, default=0.01, help="Margem no extent 'data'.")

    # ortho
    p.add_argument("--center-lon", type=float, default=-50.0, help="Centro lon ortho.")
    p.add_argument("--center-lat", type=float, default=-15.0, help="Centro lat ortho.")

    # camadas
    p.add_argument("--coast-res", default="50m", choices=["110m", "50m", "10m"],
                   help="Resolução da costa (default: 50m).")
    p.add_argument("--add-states", action="store_true", help="Adicionar estados/províncias.")
    p.add_argument("--add-lakes", action="store_true", help="Adicionar lagos.")
    p.add_argument("--save-separate", action="store_true",
                   help="Além do painel, salvar arquivos separados (plano/ortho).")

    return p.parse_args()


def main():
    args = parse_args()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(path)

    prefix = args.prefix or (path.stem + "_")

    # ler/triangular
    tri, values, lon_deg, lat_deg = load_triangulation(str(path), args.var)

    # níveis
    if args.levels:
        try:
            levels = [float(x) for x in args.levels.split(",") if x.strip() != ""]
            levels = sorted(levels)
        except Exception:
            raise ValueError("Não consegui interpretar --levels (use números separados por vírgula).")
        nlevels = None
        vmin = vmax = None
    else:
        levels = None
        nlevels = args.nlevels
        vmin, vmax = args.vmin, args.vmax

    # -------- painel --------
    fig = plt.figure(figsize=(10, 10))
    # topo: plano
    ax1 = plt.subplot(2, 1, 1, projection=ccrs.PlateCarree())
    add_common_features(ax1, coast_res=args.coast_res,
                        add_states=args.add_states, add_lakes=args.add_lakes)
    # extent do plano
    if args.extent_mode == "global":
        ax1.set_global()
    elif args.extent_mode == "data":
        a, b, c, d = _compute_extent_from_points(lon_deg, lat_deg, pad_frac=args.pad_frac)
        ax1.set_extent([a, b, c, d], crs=ccrs.PlateCarree())
    else:  # cli
        ax1.set_extent([_normalize_lon(args.lon_min), _normalize_lon(args.lon_max),
                        args.lat_min, args.lat_max], crs=ccrs.PlateCarree())
    cs1 = ax1.tricontourf(
        tri, values,
        levels=levels if levels is not None else nlevels,
        cmap=args.cmap,
        vmin=None if levels is not None else vmin,
        vmax=None if levels is not None else vmax,
        extend="both",
        transform=ccrs.PlateCarree(),
    )
    add_gridlines(ax1, labelsize=8)
    ax1.set_title("terrain height")

    # base: ortho
    proj_ortho = ccrs.Orthographic(central_longitude=args.center_lon,
                                   central_latitude=args.center_lat)
    ax2 = plt.subplot(2, 1, 2, projection=proj_ortho)
    ax2.set_global()
    add_common_features(ax2, coast_res=args.coast_res,
                        add_states=args.add_states, add_lakes=args.add_lakes)
    cs2 = ax2.tricontourf(
        tri, values,
        levels=levels if levels is not None else nlevels,
        cmap=args.cmap,
        vmin=None if levels is not None else vmin,
        vmax=None if levels is not None else vmax,
        extend="both",
        transform=ccrs.PlateCarree(),
    )

    # colorbar única ao lado direito
    cbar = fig.colorbar(cs1, ax=[ax1, ax2], orientation="vertical", fraction=0.05, pad=0.02)
    cbar.set_label("m")

    out_panel = f"{prefix}terrain_painel.png"
    plt.savefig(out_panel, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Painel salvo: {out_panel}")

    # -------- arquivos separados (opcional) --------
    if args.save_separate:
        # plano
        fig = plt.figure(figsize=(12, 5.5))
        ax = plt.axes(projection=ccrs.PlateCarree())
        add_common_features(ax, coast_res=args.coast_res,
                            add_states=args.add_states, add_lakes=args.add_lakes)
        if args.extent_mode == "global":
            ax.set_global()
        elif args.extent_mode == "data":
            a, b, c, d = _compute_extent_from_points(lon_deg, lat_deg, pad_frac=args.pad_frac)
            ax.set_extent([a, b, c, d], crs=ccrs.PlateCarree())
        else:
            ax.set_extent([_normalize_lon(args.lon_min), _normalize_lon(args.lon_max),
                           args.lat_min, args.lat_max], crs=ccrs.PlateCarree())
        cs = plot_plate(ax, tri, values, levels, vmin, vmax, args.cmap)
        add_gridlines(ax, labelsize=8)
        plt.colorbar(cs, ax=ax, orientation="horizontal", pad=0.06, fraction=0.06, extend="both").set_label("m")
        out = f"{prefix}terrain_plano.png"
        plt.savefig(out, dpi=300, bbox_inches="tight"); plt.close(fig)
        print(f"Plano salvo: {out}")

        # ortho
        fig = plt.figure(figsize=(8, 8))
        ax = plt.axes(projection=proj_ortho)
        ax.set_global()
        add_common_features(ax, coast_res=args.coast_res,
                            add_states=args.add_states, add_lakes=args.add_lakes)
        cs = plot_ortho(ax, tri, values, levels, vmin, vmax, args.cmap)
        plt.colorbar(cs, ax=ax, orientation="vertical", pad=0.02, fraction=0.05, extend="both").set_label("m")
        out = f"{prefix}terrain_ortho.png"
        plt.savefig(out, dpi=300, bbox_inches="tight"); plt.close(fig)
        print(f"Ortho salvo: {out}")


if __name__ == "__main__":
    main()
