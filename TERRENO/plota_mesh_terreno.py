#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plota_mesh_terreno.py — Versão Python do NCL (mpas_6.ncl)

- Plano (Plate Carrée): por padrão usa limites min/max do dado (--extent-mode data)
- Ortho (Orthographic): globo (hemisfério) centrado em --center-lon/--center-lat
- Preenchimento por CÉLULA (PolyCollection) da variável (--var, default 'ter')
- Níveis explícitos (--levels) OU vmin/vmax contínuo
- Colormap truncável (--cmap-trunc 0.17,1.0)
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm, Normalize, ListedColormap, LinearSegmentedColormap
import matplotlib.cm as cm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.path as mpath

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


def _unwrap_ring_lons(lons: np.ndarray) -> np.ndarray:
    """
    Desfaz saltos >180° ao longo do anel (para polígonos cruzando o antimeridiano).
    Mantém continuidade relativa ao vértice anterior.
    """
    lons = lons.astype(float).copy()
    for k in range(1, lons.size):
        while (lons[k] - lons[k - 1]) > 180.0:
            lons[k] -= 360.0
        while (lons[k] - lons[k - 1]) < -180.0:
            lons[k] += 360.0
    return lons


def _truncated_cmap(name: str, a: float, b: float, N: int = 256):
    """Retorna um colormap truncado no intervalo [a,b] de um colormap base."""
    base = cm.get_cmap(name, 256)
    a = max(0.0, min(1.0, a))
    b = max(0.0, min(1.0, b))
    if b <= a:
        b = a + 1e-6
    colors = base(np.linspace(a, b, N))
    try:
        return ListedColormap(colors)
    except Exception:
        return LinearSegmentedColormap.from_list(f"trunc_{name}", colors, N)


def _compute_extent_from_polys(polys, pad_frac: float = 0.01):
    """
    Calcula [lon_min, lon_max, lat_min, lat_max] a partir dos polígonos.
    Aplica margem relativa (pad_frac).
    """
    lons = []
    lats = []
    for p in polys:
        if p is None:
            continue
        lons.append(p[:, 0])
        lats.append(p[:, 1])
    if not lons:
        # fallback global
        return -180.0, 180.0, -90.0, 90.0

    lons = _normalize_lon(np.concatenate(lons))
    lats = np.concatenate(lats)

    lon_min = float(np.min(lons)); lon_max = float(np.max(lons))
    lat_min = float(np.min(lats)); lat_max = float(np.max(lats))

    # margem
    dx = (lon_max - lon_min) * pad_frac
    dy = (lat_max - lat_min) * pad_frac
    return lon_min - dx, lon_max + dx, lat_min - dy, lat_max + dy


# -------------- leitura: polígonos e valores por célula -------------- #
def read_mpas_cells(path_nc: str, varname: str):
    """
    Prepara polígonos por célula (lista de arrays (Ni,2) com (lon,lat) em graus)
    e valores da variável 'varname' por célula.

    Retorna:
      polys: list[np.ndarray(Ni,2)]
      vals:  np.ndarray(nCells,)
    """
    ds = _open_dataset_with_fallback(path_nc, decode_cf=False)

    # vértices em graus
    lonVertex = np.degrees(ds["lonVertex"].values).astype(np.float64)   # (nVertices,)
    latVertex = np.degrees(ds["latVertex"].values).astype(np.float64)   # (nVertices,)

    # conectividade células → vértices
    verticesOnCell = ds["verticesOnCell"].values.astype(np.int64) - 1   # (nCells, maxEdges)
    if "nEdgesOnCell" in ds:
        nEdgesOnCell = ds["nEdgesOnCell"].values.astype(np.int64)       # (nCells,)
    else:
        nEdgesOnCell = (verticesOnCell >= 0).sum(axis=1).astype(np.int64)

    nCells = verticesOnCell.shape[0]

    # variável alvo (e.g., 'ter')
    if varname not in ds.variables:
        ds.close()
        raise KeyError(f"Variável '{varname}' não encontrada no arquivo.")
    var = ds[varname].values

    # reduz para (nCells,)
    if var.ndim == 1 and var.shape[0] == nCells:
        vals = var
    elif var.ndim == 2:
        if var.shape[0] == nCells:
            vals = var[:, 0]
        elif var.shape[1] == nCells:
            vals = var[0, :]
        else:
            raise ValueError(f"Dimensões de '{varname}' inesperadas: {var.shape}")
    else:
        # pega primeiro índice nas dims à esquerda de nCells
        axis = None
        for i, s in enumerate(var.shape):
            if s == nCells:
                axis = i
                break
        if axis is None:
            raise ValueError(f"Dimensões de '{varname}' não incluem nCells: {var.shape}")
        index = [0] * var.ndim
        index[axis] = slice(None)
        vals = var[tuple(index)]

    # constrói polígonos
    polys = []
    for i in range(nCells):
        ne = int(nEdgesOnCell[i])
        if ne <= 2:
            polys.append(None)
            continue
        vs = verticesOnCell[i, :ne]
        ring_lons = _unwrap_ring_lons(lonVertex[vs])
        ring_lats = latVertex[vs]
        # fecha anel (opcional)
        if ring_lons[0] != ring_lons[-1] or ring_lats[0] != ring_lats[-1]:
            ring_lons = np.append(ring_lons, ring_lons[0])
            ring_lats = np.append(ring_lats, ring_lats[0])
        poly = np.stack([ring_lons, ring_lats], axis=1)
        polys.append(poly)

    ds.close()
    return polys, np.asarray(vals, dtype=float)


# ---------------- desenho ---------------- #
def add_base_features(ax, coastline_res: str = "50m"):
    ax.coastlines(resolution=coastline_res, linewidth=0.6)
    ax.add_feature(cfeature.BORDERS, linewidth=0.2)


def draw_cells(ax, polys, vals, cmap_name="terrain", cmap_trunc=(0.17, 1.0),
               levels=None, vmin=None, vmax=None):
    """
    Desenha as células como PolyCollection, com colorbar.
    - levels: lista de níveis explícitos (BoundaryNorm) OU
    - vmin/vmax: escala contínua (Normalize)
    """
    good = [(p, v) for p, v in zip(polys, vals) if (p is not None) and np.isfinite(v)]
    if not good:
        return None

    polys_good, vals_good = zip(*good)
    vals_good = np.asarray(vals_good, dtype=float)

    cmap = _truncated_cmap(cmap_name, cmap_trunc[0], cmap_trunc[1])

    coll = PolyCollection(
        polys_good,
        edgecolors="none",
        transform=ccrs.PlateCarree(),
        zorder=3,
    )

    if levels is not None and len(levels) >= 2:
        norm = BoundaryNorm(levels, ncolors=cmap.N, clip=True)
    else:
        norm = Normalize(vmin=vmin, vmax=vmax)

    coll.set_cmap(cmap)
    coll.set_norm(norm)
    coll.set_array(vals_good)

    ax.add_collection(coll)

    cb = plt.colorbar(coll, ax=ax, orientation="vertical", shrink=0.8, pad=0.02)
    cb.ax.tick_params(labelsize=8)

    return coll


def plot_planar(polys, vals, out_png, title, coast_res,
                lon_min, lon_max, lat_min, lat_max,
                cmap_name, cmap_trunc, levels, vmin, vmax):
    fig = plt.figure(figsize=(11, 8.5))
    ax = plt.axes(projection=ccrs.PlateCarree())
    add_base_features(ax, coastline_res=coast_res)
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

    draw_cells(ax, polys, vals, cmap_name=cmap_name, cmap_trunc=cmap_trunc,
               levels=levels, vmin=vmin, vmax=vmax)

    if title:
        ax.set_title(title, fontsize=12)

    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_orthographic(polys, vals, out_png, title, coast_res,
                      center_lon, center_lat,
                      cmap_name, cmap_trunc, levels, vmin, vmax):
    fig = plt.figure(figsize=(10, 10))
    ax = plt.axes(projection=ccrs.Orthographic(
        central_longitude=center_lon, central_latitude=center_lat
    ))

    ax.set_global()  # domínio global
    # --- define um boundary circular no espaço de eixos (0..1), que vira o "globo"
    theta = np.linspace(0, 2*np.pi, 361)
    circle = np.column_stack([np.cos(theta), np.sin(theta)])
    circle_path = mpath.Path(circle * 0.5 + 0.5)  # raio=0.5, centro=(0.5,0.5)
    ax.set_boundary(circle_path, transform=ax.transAxes)

    add_base_features(ax, coastline_res=coast_res)

    coll = draw_cells(ax, polys, vals,
                      cmap_name=cmap_name, cmap_trunc=cmap_trunc,
                      levels=levels, vmin=vmin, vmax=vmax)

    # Clip explícito à patch do eixo (que agora é circular)
    if coll is not None:
        coll.set_clip_path(ax.patch)

    # estética opcional
    ax.outline_patch.set_linewidth(0.6) if hasattr(ax, "outline_patch") else None
    ax.set_facecolor("#cfe8ff")  # oceano de fundo

    if title:
        ax.set_title(title, fontsize=12)

    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)




# ---------------- CLI ---------------- #
def parse_args():
    p = argparse.ArgumentParser(
        description="Plota variável de terreno/uso do solo do MPAS por célula (raster fill)."
    )
    # arquivo posicional/flag
    p.add_argument("--input", "-i", default=None, help="Arquivo MPAS init/grid (ex.: init.nc)")
    p.add_argument("input_pos", nargs="?", default=None, help="Arquivo MPAS init/grid (ex.: init.nc)")

    # prefixo (flag ou 2º posicional)
    p.add_argument("--prefix", "-p", default=None,
                   help="Prefixo dos PNGs. Se omitido, usa <stem do arquivo>_ .")
    p.add_argument("prefix_pos", nargs="?", default=None,
                   help="Prefixo dos PNGs (opcional).")

    # variável e paleta
    p.add_argument("--var", default="ter", help="Variável por célula a plotar. Default: ter")
    p.add_argument("--cmap", default="terrain", help="Colormap base. Default: terrain")
    p.add_argument("--cmap-trunc", default="0.17,1.0",
                   help="Fatia do colormap no intervalo [a,b], ex.: 0.17,1.0 (default).")

    # níveis ou vmin/vmax
    p.add_argument("--levels", default=None,
                   help="Lista de níveis explícitos separada por vírgulas (ex.: 50,100,250,...)")
    p.add_argument("--vmin", type=float, default=None, help="Escala contínua: mínimo.")
    p.add_argument("--vmax", type=float, default=None, help="Escala contínua: máximo.")

    # mapa
    p.add_argument("--coast-res", default="50m", choices=["110m", "50m", "10m"],
                   help="Resolução de costa Cartopy. Default: 50m")
    p.add_argument("--title", default="MPAS – Terreno e Uso de Solo",
                   help="Título do mapa (default igual ao NCL).")

    # extensão do plano (modo)
    p.add_argument("--extent-mode", choices=["data", "cli", "global"], default="data",
                   help="Como definir o extent do PLANO: data=min/max do dado (default), cli=usa --lon/lat, global=tudo.")

    # se usar extent cli
    p.add_argument("--lon-min", type=float, default=-80.0,
                   help="Longitude mínima (0–360 ou -180–180) para --extent-mode cli.")
    p.add_argument("--lon-max", type=float, default=-30.0,
                   help="Longitude máxima (0–360 ou -180–180) para --extent-mode cli.")
    p.add_argument("--lat-min", type=float, default=-50.0,
                   help="Latitude mínima para --extent-mode cli.")
    p.add_argument("--lat-max", type=float, default=10.0,
                   help="Latitude máxima para --extent-mode cli.")

    # margem quando extent = data
    p.add_argument("--pad-frac", type=float, default=0.01,
                   help="Margem relativa no extent 'data' (default: 0.01 = 1%).")

    # centro ortográfico
    p.add_argument("--center-lon", type=float, default=-50.0,
                   help="Longitude central da projeção Ortográfica. Default: -50")
    p.add_argument("--center-lat", type=float, default=-15.0,
                   help="Latitude central da projeção Ortográfica. Default: -15")

    return p.parse_args()


def main():
    args = parse_args()

    # arquivo: flag > posicional > "init.nc"
    path_nc = args.input or args.input_pos or "init.nc"
    path_nc = Path(path_nc)
    if not path_nc.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path_nc}")

    # prefixo: flag > posicional > stem_
    prefix = args.prefix or args.prefix_pos or (path_nc.stem + "_")
    out_planar = f"{prefix}plano.png"
    out_ortho  = f"{prefix}ortho.png"

    # parse cmap truncation
    try:
        a_str, b_str = args.cmap_trunc.split(",")
        cmap_trunc = (float(a_str), float(b_str))
    except Exception:
        cmap_trunc = (0.17, 1.0)

    # níveis explícitos (se fornecidos)
    levels = None
    if args.levels:
        try:
            levels = [float(x) for x in args.levels.split(",") if x.strip() != ""]
            levels = sorted(levels)
        except Exception:
            raise ValueError("Não foi possível interpretar --levels. Use números separados por vírgulas.")

    # leitura
    polys, vals = read_mpas_cells(str(path_nc), args.var)

    # decide extent do PLANO
    if args.extent_mode == "global":
        lon_min, lon_max, lat_min, lat_max = -180.0, 180.0, -90.0, 90.0
    elif args.extent_mode == "cli":
        lon_min = _normalize_lon(args.lon_min)
        lon_max = _normalize_lon(args.lon_max)
        lat_min = float(args.lat_min)
        lat_max = float(args.lat_max)
    else:  # data
        lon_min, lon_max, lat_min, lat_max = _compute_extent_from_polys(polys, pad_frac=args.pad_frac)

    # mapas
    plot_planar(polys, vals, out_planar, args.title, args.coast_res,
                lon_min, lon_max, lat_min, lat_max,
                args.cmap, cmap_trunc, levels, args.vmin, args.vmax)

    plot_orthographic(polys, vals, out_ortho, args.title, args.coast_res,
                      args.center_lon, args.center_lat,
                      args.cmap, cmap_trunc, levels, args.vmin, args.vmax)

    print("Figuras salvas:")
    print(f"  {out_planar}")
    print(f"  {out_ortho}")
    if levels:
        print(f"Níveis: {levels}")
    else:
        print(f"vmin/vmax: {args.vmin} / {args.vmax}")
    print(f"PLANO extent ({args.extent_mode}): lon=({lon_min:.3f},{lon_max:.3f}), lat=({lat_min:.3f},{lat_max:.3f})")
    print(f"ORTHO center: lon={args.center_lon}, lat={args.center_lat}")


if __name__ == "__main__":
    main()
