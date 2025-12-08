#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mpas_plota_chuva.py
Gera mapas de chuva acumulada do MPAS (total do período e diários).

- Usa a malha MPAS do arquivo --init (centroides e polígonos das células)
- Lê rainc e rainnc dos arquivos --data (history.* ou diag.*)
- Calcula acumulados por diferença entre tempos
- Plota:
    (a) malha nativa MPAS (cada célula preenchida)
    (b) opcionalmente grade regular lat/lon via --interp --res 0.5

Saídas:
    <prefix>_total_native.png
    <prefix>_total_latlon_0.5deg.png (se --interp)
    <prefix>_daily_YYYYMMDD_native.png (se --daily)
    <prefix>_daily_YYYYMMDD_latlon_0.5deg.png (se --daily --interp)

Dependências:
    numpy, xarray, matplotlib, cartopy, scipy
"""

import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from datetime import datetime, timedelta
from scipy.interpolate import griddata


# -------------------------------------------------
# Helpers gerais
# -------------------------------------------------

def time_to_str(t):
    """
    Converte qualquer tipo de timestamp (numpy.datetime64, cftime, datetime)
    para string amigável. Evita crash do np.datetime_as_string em cftime.
    """
    try:
        return np.datetime_as_string(np.datetime64(t))
    except Exception:
        return str(t)


# -------------------------------------------------
# Utilidades de malha MPAS
# -------------------------------------------------

def load_mesh_geometry(init_file):
    """
    Lê info geométrica da malha MPAS a partir do arquivo --init.

    Funciona tanto para malhas onde:
      verticesOnCell(maxEdgesOnCell, nCells)
    quanto para:
      verticesOnCell(nCells, maxEdgesOnCell)

    Retorna:
      cell_lon (nCells,)   em graus [-180,180]
      cell_lat (nCells,)   em graus
      cell_polys_lonlat : lista de polígonos [(lon,lat), ...] por célula
    """
    ds = xr.open_dataset(init_file)

    # centroides (radianos -> graus)
    cell_lat = np.degrees(ds["latCell"].values)   # (nCells,)
    cell_lon = np.degrees(ds["lonCell"].values)   # (nCells,)

    # normaliza longitudes dos centróides pra [-180,180]
    cell_lon = np.where(cell_lon > 180.0, cell_lon - 360.0, cell_lon)

    # vértices globais
    latVertex = np.degrees(ds["latVertex"].values)  # (nVertices,)
    lonVertex = np.degrees(ds["lonVertex"].values)
    lonVertex = np.where(lonVertex > 180.0, lonVertex - 360.0, lonVertex)

    # conectividade vértices→célula
    voc_raw = ds["verticesOnCell"].values
    nEdgesOnCell = ds["nEdgesOnCell"].values  # (nCells,)
    nCells = ds.sizes["nCells"]

    # Detectar orientação de verticesOnCell
    # Caso 1: (maxEdgesOnCell, nCells)
    # Caso 2: (nCells, maxEdgesOnCell)
    if voc_raw.shape[1] == nCells:
        verticesOnCell = voc_raw
    elif voc_raw.shape[0] == nCells:
        verticesOnCell = voc_raw.T
    else:
        ds.close()
        raise RuntimeError(
            f"Formato inesperado de verticesOnCell: {voc_raw.shape}. "
            "Não consegui associar às células."
        )

    maxEdgesOnCell = verticesOnCell.shape[0]

    # monta lista de polígonos por célula
    cell_polys_lonlat = []
    for iCell in range(nCells):
        nEdges = nEdgesOnCell[iCell]
        if nEdges > maxEdgesOnCell:
            ds.close()
            raise RuntimeError(
                f"Para a célula {iCell}, nEdges={nEdges} > maxEdgesOnCell={maxEdgesOnCell}. "
                "Inconsistência na malha."
            )

        # MPAS armazena índices 1-based -> vira 0-based
        verts_idx = verticesOnCell[:nEdges, iCell] - 1
        lons = lonVertex[verts_idx]
        lats = latVertex[verts_idx]

        poly = np.column_stack([lons, lats])  # [(lon,lat), ...]
        cell_polys_lonlat.append(poly)

    ds.close()
    return cell_lon, cell_lat, cell_polys_lonlat


# -------------------------------------------------
# Leitura de chuva e recorte temporal
# -------------------------------------------------

def open_concat_data(data_files):
    """
    Abre um ou mais arquivos MPAS (history.*, diag.*) sem usar dask,
    concatena ao longo de Time, e garante rainc/rainnc + ordenação temporal.

    Retorna: ds_merge (xarray.Dataset)
    """
    ds_list = []
    for f in data_files:
        ds_here = xr.open_dataset(
            f,
            decode_times=True,
        )
        ds_list.append(ds_here)

    if len(ds_list) == 1:
        ds_merge = ds_list[0]
    else:
        ds_merge = xr.concat(ds_list, dim="Time", combine_attrs="override")

    # garantir que temos as variáveis necessárias
    for v in ["rainc", "rainnc"]:
        if v not in ds_merge.variables:
            raise ValueError(f"Variável {v} não encontrada nos arquivos de dados ({v} ausente).")

    # garantir que temos Time
    if "Time" not in ds_merge.dims and "Time" not in ds_merge.coords:
        raise ValueError("Não encontrei a dimensão Time nos arquivos passados.")

    # ordena cronologicamente
    ds_merge = ds_merge.sortby("Time")

    return ds_merge


def select_timerange(ds, start_str=None, end_str=None):
    """
    Recorta dataset entre start e end (inclusive start, inclusive end).
    Se não definidos, usa o range completo.
    """
    t_all = ds["Time"].values  # np.datetime64[] ou cftime[]
    tmin = t_all[0]
    tmax = t_all[-1]

    if start_str is not None:
        tmin = np.datetime64(start_str)
    if end_str is not None:
        tmax = np.datetime64(end_str)

    ds_sel = ds.sel(Time=slice(tmin, tmax))
    return ds_sel


def accumulated_between(ds, t0, t1):
    """
    Calcula chuva acumulada entre dois tempos t0 e t1:
      total = (rainc+rainnc)[t1] - (rainc+rainnc)[t0]
    Retorna array (nCells,)
    """
    rain_tot = ds["rainc"] + ds["rainnc"]
    arr0 = rain_tot.sel(Time=t0).values  # (nCells,)
    arr1 = rain_tot.sel(Time=t1).values
    acum = arr1 - arr0

    # Se acumulador resetou (valores negativos), zera
    acum = np.where(acum < 0, 0, acum)

    # Se estiver em metros de água equivalente em vez de mm,
    # você pode fazer: acum = acum * 1000.0
    return acum


def compute_total_period_accum(ds_sel):
    """
    Usa primeiro e último tempo disponíveis em ds_sel
    para gerar o acumulado total do período.
    """
    t_list = ds_sel["Time"].values
    t0 = t_list[0]
    t1 = t_list[-1]
    return accumulated_between(ds_sel, t0, t1), t0, t1


def daterange_days(t_start, t_end):
    """
    Gera lista de dias UTC cobrindo [t_start, t_end] inclusive início,
    até o último dia começado dentro do intervalo.
    Ex: 2024-05-20 03Z até 2024-05-22 18Z -> [2024-05-20, 2024-05-21, 2024-05-22]

    Observação: convertemos pra datetime "naive" (sem TZ) pra poder fazer loops.
    """
    d0 = np.datetime_as_string(t_start, timezone="naive")
    d1 = np.datetime_as_string(t_end,   timezone="naive")
    d0 = datetime.fromisoformat(d0.replace("Z", ""))  # remove 'Z' se existir
    d1 = datetime.fromisoformat(d1.replace("Z", ""))

    days = []
    cur = datetime(d0.year, d0.month, d0.day)
    end_day = datetime(d1.year, d1.month, d1.day)
    while cur <= end_day:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def compute_daily_accum(ds_sel):
    """
    Para cada dia dentro do intervalo temporal de ds_sel,
    calcula acumulado 00:00Z -> 24:00Z (ou até último tempo disponível daquele dia).
    Usa intervalo [00Z, 24Z) (fechado-aberto), pra não contaminar o dia D com 00Z do D+1.

    Retorna dict:
      {
        'YYYYMMDD': (acum_array, tA, tB)
      }
    onde acum_array tem shape (nCells,)
    """
    out = {}
    t_all = ds_sel["Time"].values
    global_start = t_all[0]
    global_end   = t_all[-1]

    # Lista de dias cobertos
    days = daterange_days(global_start, global_end)

    rain_tot = ds_sel["rainc"] + ds_sel["rainnc"]

    for d in days:
        # janela daquele dia [d 00Z, d+1 00Z)
        day_start = np.datetime64(d.isoformat() + "T00:00:00")
        day_end   = np.datetime64((d + timedelta(days=1)).isoformat() + "T00:00:00")

        # tempos dentro desse dia
        mask_day = (t_all >= day_start) & (t_all < day_end)
        t_day = t_all[mask_day]

        # precisa ter pelo menos 2 tempos pra fazer diferença
        if t_day.size < 2:
            continue

        t0 = t_day[0]
        t1 = t_day[-1]

        arr0 = rain_tot.sel(Time=t0).values
        arr1 = rain_tot.sel(Time=t1).values
        acum = arr1 - arr0
        acum = np.where(acum < 0, 0, acum)

        day_id = d.strftime("%Y%m%d")
        out[day_id] = (acum, t0, t1)

    return out


# -------------------------------------------------
# Funções auxiliares de extent
# -------------------------------------------------

def _auto_extent_from_polys(polys_lonlat, pad_deg=2.0):
    """
    Calcula limites [lon_min, lon_max, lat_min, lat_max] dos polígonos da malha,
    com uma borda extra pad_deg em graus.
    """
    all_lons = np.concatenate([p[:, 0] for p in polys_lonlat])
    all_lats = np.concatenate([p[:, 1] for p in polys_lonlat])

    lon_min = np.nanmin(all_lons) - pad_deg
    lon_max = np.nanmax(all_lons) + pad_deg
    lat_min = np.nanmin(all_lats) - pad_deg
    lat_max = np.nanmax(all_lats) + pad_deg

    return [lon_min, lon_max, lat_min, lat_max]


def _auto_extent_from_grid(lon2d, lat2d, pad_deg=2.0):
    """
    Calcula limites [lon_min, lon_max, lat_min, lat_max] de uma grade regular.
    """
    lon_min = np.nanmin(lon2d) - pad_deg
    lon_max = np.nanmax(lon2d) + pad_deg
    lat_min = np.nanmin(lat2d) - pad_deg
    lat_max = np.nanmax(lat2d) + pad_deg
    return [lon_min, lon_max, lat_min, lat_max]


# -------------------------------------------------
# Plot em malha nativa
# -------------------------------------------------

def plot_native_polygon_map(polys_lonlat, values, title, outfile,
                            vmin=None, vmax=None,
                            cmap="turbo",
                            extent=None):
    """
    Desenha cada célula MPAS como um polígono colorido na projeção PlateCarree.
    """
    # Normalize cores
    if vmin is None:
        vmin = np.nanmin(values)
    if vmax is None:
        vmax = np.nanmax(values)
    norm = Normalize(vmin=vmin, vmax=vmax)

    # montar PolyCollection
    poly_verts = []
    face_colors = []
    for poly, val in zip(polys_lonlat, values):
        poly_verts.append(poly)
        face_colors.append(val)
    face_colors = np.array(face_colors)

    pcoll = PolyCollection(
        poly_verts,
        array=face_colors,
        cmap=cmap,
        norm=norm,
        edgecolors='none',
        linewidths=0.0,
        closed=True,
        transform=ccrs.PlateCarree(),
    )

    fig = plt.figure(figsize=(10, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.add_collection(pcoll)

    ax.coastlines(resolution='110m', linewidth=0.6)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4)

    # Se o usuário passou --extent, respeita. Caso contrário, calcula automático.
    if extent is not None:
        latmin, latmax, lonmin, lonmax = extent
        ax.set_extent([lonmin, lonmax, latmin, latmax], crs=ccrs.PlateCarree())
    else:
        lon_min, lon_max, lat_min, lat_max = _auto_extent_from_polys(polys_lonlat)
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

    cb = plt.colorbar(
        pcoll,
        ax=ax,
        orientation='horizontal',
        pad=0.05,
        label="Precipitação acumulada (mm)"
    )
    ax.set_title(title)

    plt.savefig(outfile, dpi=200, bbox_inches='tight')
    plt.close(fig)


# -------------------------------------------------
# Interpolação para grade lat/lon regular
# -------------------------------------------------

def interpolate_to_latlon(cell_lon, cell_lat, values, res_deg):
    """
    Interpola valores nos centróides de célula MPAS (lon/lat de cada célula)
    para uma grade regular lat/lon.

    res_deg = resolução em graus, ex: 0.5 -> 0.5°
    Retorna:
      lon2d, lat2d, grid_vals
    """
    # normalizar longitude para [-180,180]
    lon_fix = np.where(cell_lon > 180.0, cell_lon - 360.0, cell_lon)
    lat_fix = cell_lat

    # grade alvo global (a gente faz zoom no plot depois)
    lon_grid = np.arange(-180.0, 180.0 + res_deg, res_deg)
    lat_grid = np.arange(-90.0,   90.0  + res_deg, res_deg)
    lon2d, lat2d = np.meshgrid(lon_grid, lat_grid)

    # interpolação espacial (linear). pontos = centróides.
    points = np.column_stack([lon_fix, lat_fix])
    grid_vals = griddata(points, values, (lon2d, lat2d), method="linear")

    return lon2d, lat2d, grid_vals


def plot_latlon_grid(lon2d, lat2d, grid_vals, title, outfile,
                     vmin=None, vmax=None,
                     cmap="turbo",
                     extent=None):
    """
    Plota matriz regular em PlateCarree com pcolormesh.
    Faz zoom na área de interesse (--extent ou automático).
    """
    if vmin is None:
        vmin = np.nanmin(grid_vals)
    if vmax is None:
        vmax = np.nanmax(grid_vals)

    fig = plt.figure(figsize=(10, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())

    pcm = ax.pcolormesh(
        lon2d, lat2d, grid_vals,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading='auto',
        transform=ccrs.PlateCarree()
    )

    ax.coastlines(resolution='110m', linewidth=0.6)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4)

    # Zoom: se --extent veio, usa. Senão faz automático baseado na grade.
    if extent is not None:
        latmin, latmax, lonmin, lonmax = extent
        ax.set_extent([lonmin, lonmax, latmin, latmax], crs=ccrs.PlateCarree())
    else:
        lon_min, lon_max, lat_min, lat_max = _auto_extent_from_grid(lon2d, lat2d)
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())

    cb = plt.colorbar(
        pcm,
        ax=ax,
        orientation='horizontal',
        pad=0.05,
        label="Precipitação acumulada (mm)"
    )
    ax.set_title(title)

    plt.savefig(outfile, dpi=200, bbox_inches='tight')
    plt.close(fig)


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Gera mapas de chuva acumulada (total e diária) de saídas MPAS."
    )
    parser.add_argument("--init", required=True,
                        help="Arquivo init da malha MPAS (ex: x1.40962.init.nc)")
    parser.add_argument("--data", nargs="+", required=True,
                        help="Arquivos history.*.nc / diag*.nc (1 ou mais)")
    parser.add_argument("--start", default=None,
                        help='Início do período (ex: "2024-05-20_00:00:00"). Opcional.')
    parser.add_argument("--end", default=None,
                        help='Fim do período (ex: "2024-05-21_00:00:00"). Opcional.')
    parser.add_argument("--daily", action="store_true",
                        help="Também gerar mapas diários.")
    parser.add_argument("--interp", action="store_true",
                        help="Interpolar também para grade lat/lon regular.")
    parser.add_argument("--res", type=float, default=0.5,
                        help="Resolução em graus da grade regular (default 0.5).")
    parser.add_argument("--vmin", type=float, default=None,
                        help="Escala mínima (mm) para plots.")
    parser.add_argument("--vmax", type=float, default=None,
                        help="Escala máxima (mm) para plots.")
    parser.add_argument("--cmap", default="turbo",
                        help="Colormap matplotlib (default turbo).")
    parser.add_argument("--outdir", default=".",
                        help="Diretório de saída dos PNGs.")
    parser.add_argument("--prefix", default="rain",
                        help="Prefixo dos nomes de arquivo de saída.")
    parser.add_argument("--extent", nargs=4, type=float,
                        metavar=("LATMIN", "LATMAX", "LONMIN", "LONMAX"),
                        help="Limites manuais do mapa: LATMIN LATMAX LONMIN LONMAX (graus).")

    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 1. Lê malha (geometria)
    cell_lon, cell_lat, cell_polys_lonlat = load_mesh_geometry(args.init)

    # 2. Lê dados de chuva (rainc/rainnc) sem dask
    ds_all = open_concat_data(args.data)

    # 3. Recorta tempo se solicitado
    ds_sel = select_timerange(ds_all, start_str=args.start, end_str=args.end)

    # 4. Acumulado total no período selecionado
    total_acum, t0, t1 = compute_total_period_accum(ds_sel)

    # 5. Plot acumulado total na malha nativa
    title_total = (
        f"Chuva acumulada total (mm)\n{time_to_str(t0)} → {time_to_str(t1)}"
    )
    outfile_total_native = outdir / f"{args.prefix}_total_native.png"
    plot_native_polygon_map(
        cell_polys_lonlat,
        total_acum,
        title_total,
        outfile_total_native,
        vmin=args.vmin,
        vmax=args.vmax,
        cmap=args.cmap,
        extent=args.extent,
    )

    # 6. Se --interp, faz interpolação e plota o acumulado total na grade regular
    if args.interp:
        lon2d, lat2d, grid_vals = interpolate_to_latlon(
            cell_lon, cell_lat, total_acum, res_deg=args.res
        )
        outfile_total_latlon = outdir / f"{args.prefix}_total_latlon_{args.res}deg.png"
        plot_latlon_grid(
            lon2d,
            lat2d,
            grid_vals,
            title_total,
            outfile_total_latlon,
            vmin=args.vmin,
            vmax=args.vmax,
            cmap=args.cmap,
            extent=args.extent,
        )

    # 7. Se --daily, gera acumulados diários e plota
    if args.daily:
        daily_dict = compute_daily_accum(ds_sel)
        for day_id, (acum_day, td0, td1) in daily_dict.items():
            title_day = (
                f"Chuva diária (mm) {day_id}\n{time_to_str(td0)} → {time_to_str(td1)}"
            )

            # malha nativa
            outfile_day_native = outdir / f"{args.prefix}_daily_{day_id}_native.png"
            plot_native_polygon_map(
                cell_polys_lonlat,
                acum_day,
                title_day,
                outfile_day_native,
                vmin=args.vmin,
                vmax=args.vmax,
                cmap=args.cmap,
                extent=args.extent,
            )

            # interpolado opcional
            if args.interp:
                lon2d_d, lat2d_d, grid_vals_d = interpolate_to_latlon(
                    cell_lon, cell_lat, acum_day, res_deg=args.res
                )
                outfile_day_latlon = outdir / (
                    f"{args.prefix}_daily_{day_id}_latlon_{args.res}deg.png"
                )
                plot_latlon_grid(
                    lon2d_d,
                    lat2d_d,
                    grid_vals_d,
                    title_day,
                    outfile_day_latlon,
                    vmin=args.vmin,
                    vmax=args.vmax,
                    cmap=args.cmap,
                    extent=args.extent,
                )

    # Fecha datasets
    ds_all.close()
    ds_sel.close()


if __name__ == "__main__":
    main()
