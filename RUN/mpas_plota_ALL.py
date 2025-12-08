#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import argparse
import sys
import re
from pathlib import Path

try:
    from scipy.spatial import cKDTree
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False


# ==============================================================
# UTILIDADES BÁSICAS
# ==============================================================

def _lon_wrap(lon_deg):
    """Normaliza longitude para [-180,180]."""
    return ((lon_deg + 180.0) % 360.0) - 180.0


def _decode_xtime_index(ds, t_idx):
    """
    Lê ds['xtime'].isel(Time=t_idx) e retorna string bruta 'YYYY-MM-DD_HH:MM:SS'
    independente de ser escalar 0-D ou array de chars.
    Se xtime não existir ou algo falhar, retorna None.
    """
    if "xtime" not in ds:
        return None
    try:
        xt = ds["xtime"].isel(Time=t_idx).values
    except Exception:
        return None

    # Caso escalar 0-D
    if isinstance(xt, np.ndarray) and xt.ndim == 0:
        s = xt.tobytes().decode("utf-8", errors="ignore")
    # Caso array de chars 1-D/2-D
    elif isinstance(xt, np.ndarray):
        chars = []
        for c in xt.ravel():
            if isinstance(c, (bytes, bytearray)):
                chars.append(c.decode("utf-8", errors="ignore"))
            else:
                chars.append(str(c))
        s = "".join(chars)
    # Caso bytes direto
    elif isinstance(xt, (bytes, bytearray)):
        s = xt.decode("utf-8", errors="ignore")
    else:
        s = str(xt)

    s = s.replace("\x00", "").strip()
    return s or None


def _timestamp_from_raw_string(raw):
    """
    Recebe algo tipo '2024-05-20_00:00:00' e devolve ('20052024','0000').
    Se tiver só data, devolve ('20052024','0000').
    Se nada servir, devolve ('sem_tempo','sem_tempo').
    """
    if not raw:
        return "sem_tempo", "sem_tempo"

    txt = raw.replace("_", " ").replace("T", " ")

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[ T]+(\d{2}):(\d{2})", txt)
    if m:
        yyyy, mm, dd, hh, mi = m.groups()
        return f"{dd}{mm}{yyyy}", f"{hh}{mi}"

    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt)
    if m2:
        yyyy, mm, dd = m2.groups()
        return f"{dd}{mm}{yyyy}", "0000"

    return "sem_tempo", "sem_tempo"


def _timestamp_from_filename(fname):
    """
    Fallback: tenta extrair tempo do nome do arquivo history.YYYY-MM-DD_HH.MM.SS.nc
    Retorna ('DDMMAAAA','HHMM') ou ('sem_tempo','sem_tempo').
    """
    if fname is None:
        return "sem_tempo", "sem_tempo"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})\.(\d{2})", str(fname))
    if m:
        yyyy, mm, dd, hh, mi = m.groups()
        return f"{dd}{mm}{yyyy}", f"{hh}{mi}"
    return "sem_tempo", "sem_tempo"


def _get_timestamp_for_time_index(ds, t_idx, tempo_cli=None, fname=None):
    """
    Decide qual timestamp usar para UM índice de tempo t_idx.
    Ordem de prioridade:
    1. --tempo (tempo_cli)
    2. xtime(Time=t_idx)
    3. nome do arquivo
    """
    # 1. forçado via CLI
    if tempo_cli:
        forced = tempo_cli.replace("_", " ").replace("T", " ")
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})[ T]+(\d{2}):(\d{2})", forced)
        if m:
            yyyy, mm, dd, hh, mi = m.groups()
            return f"{dd}{mm}{yyyy}", f"{hh}{mi}"

    # 2. xtime
    raw_xtime = _decode_xtime_index(ds, t_idx)
    if raw_xtime:
        return _timestamp_from_raw_string(raw_xtime)

    # 3. fallback filename
    return _timestamp_from_filename(fname)


# ==============================================================
# PRESSÃO / NÍVEIS
# ==============================================================

def _find_pressure_var(ds, vert_dim):
    """
    Tenta achar um campo de pressão com a dimensão vertical vert_dim.
    """
    for v in ["pressure", "p", "pres", "prs", "pressureMid", "pressure_mid"]:
        if v in ds and vert_dim in ds[v].dims:
            da = ds[v]
            if "Time" in da.dims:
                # não escolher tempo ainda (vamos isolar na função que usa)
                pass
            return da
    return None


def _pick_level_from_hPa(ds, vert_dim, alvo_hPa, t_idx):
    """
    Dado um alvo em hPa, escolhe o índice vertical mais próximo.
    Faz média espacial e pega o perfil 1D de pressão.
    """
    da_p = _find_pressure_var(ds, vert_dim)
    if da_p is None:
        print("[AVISO] Nenhuma variável de pressão compatível. Ignorando --nivelhPa.")
        return None

    # Seleciona o tempo pedido (ou 0 se não tem tempo em pressão)
    if "Time" in da_p.dims:
        da_p_use = da_p.isel(Time=t_idx)
    else:
        da_p_use = da_p

    # média nas dims que não são verticais
    for d in [d for d in da_p_use.dims if d != vert_dim]:
        da_p_use = da_p_use.mean(dim=d)

    pvals = da_p_use.values  # perfil vertical
    # detectar Pa vs hPa
    if np.nanmean(pvals) > 2000.0:
        p_hPa = pvals / 100.0
    else:
        p_hPa = pvals

    idx_best = int(np.nanargmin(np.abs(p_hPa - alvo_hPa)))
    return idx_best


# ==============================================================
# EXTRAIR UMA VARIÁVEL PARA UM TEMPO ESPECÍFICO
# ==============================================================

def _select_variable_at_time(ds, varname, t_idx, nivel, nivelhPa,
                             tempo_cli, fname):
    """
    Extrai UM campo (uma DataArray 1D em nCells) para:
      - variável varname
      - tempo t_idx
      - nível vertical escolhido por --nivel ou --nivelhPa
    Retorna (da_1D, used_level)
    """
    if varname not in ds:
        print(f"\nERRO: variável '{varname}' não encontrada.")
        vars_guess = list(ds.data_vars)[:20]
        print("Algumas variáveis disponíveis:", vars_guess)
        sys.exit(1)

    da = ds[varname]

    # recorta tempo
    if "Time" in da.dims:
        if t_idx >= da.sizes["Time"]:
            print(f"\nERRO: --time-index {t_idx} fora do range (Time tem {da.sizes['Time']} instantes).")
            sys.exit(1)
        da = da.isel(Time=t_idx)

    # pega timestamp strings (ddmmaaaa, hhmm) para esse t_idx
    stamp_date, stamp_hm = _get_timestamp_for_time_index(
        ds,
        t_idx,
        tempo_cli=tempo_cli,
        fname=fname
    )
    da.attrs["stamp_date"] = stamp_date
    da.attrs["stamp_hm"]   = stamp_hm

    # detectar dimensão vertical
    vert_dim = next(
        (d for d in da.dims if any(k in d.lower() for k in ["vert", "lev", "soil"])),
        None
    )

    used_level = None
    if vert_dim:
        # decidir nível vertical
        if nivelhPa is not None:
            lvl = _pick_level_from_hPa(ds, vert_dim, nivelhPa, t_idx)
            if lvl is None:
                lvl = nivel if nivel is not None else 0
        else:
            if nivel is not None:
                lvl = nivel
            else:
                lvl = 0

        # sanity check
        max_level = da.sizes[vert_dim] - 1
        if not (0 <= lvl <= max_level):
            print(f"\nERRO: nível {lvl} fora de [0..{max_level}] para '{varname}'.")
            sys.exit(1)

        da = da.isel({vert_dim: lvl})
        used_level = lvl

    # precisa depender de nCells
    if "nCells" not in da.dims:
        print("\nERRO: variável final não tem dimensão nCells. Dimensões atuais:", da.dims)
        sys.exit(1)

    da.name = varname
    return da, used_level


# ==============================================================
# CONVERSÕES DE UNIDADE
# ==============================================================

def _convert_units(vals, da_meta, unidade_alvo):
    """
    --unidade C   : Kelvin → °C
    --unidade hPa : Pa → hPa
    default       : mantém
    """
    unidade_alvo = (unidade_alvo or "original").lower()
    orig_units = da_meta.attrs.get("units", "")
    mean_val = float(np.nanmean(vals))

    # Kelvin → Celsius
    if unidade_alvo in ["c", "celsius", "°c", "degc"]:
        if "k" in orig_units.lower() or (200.0 < mean_val < 400.0):
            return vals - 273.15, "°C"

    # Pa → hPa
    if unidade_alvo in ["hpa", "mb"]:
        if "pa" in orig_units.lower() or mean_val > 2000.0:
            return vals / 100.0, "hPa"

    return vals, (orig_units or "unidade desconhecida")


# ==============================================================
# MÁSCARA DE TERRA / OCEANO
# ==============================================================

def _pull_landmask(ds):
    if "landmask" not in ds:
        return None
    lm = ds["landmask"]
    if "Time" in lm.dims:
        lm = lm.isel(Time=0)
    return lm.values


def _load_landmask(ds_main, mask_file):
    lm_main = _pull_landmask(ds_main)
    if lm_main is not None:
        return lm_main
    if mask_file:
        try:
            ds_mask = xr.open_dataset(mask_file, decode_coords="all")
            lm_mask = _pull_landmask(ds_mask)
            return lm_mask
        except Exception as e:
            print(f"[AVISO] não consegui abrir {mask_file}: {e}")
    return None


def _apply_landmask(vals, landmask_vals, mode):
    """
    mode='land'  → remover terra (mostrar só oceano)
    mode='ocean' → remover oceano (mostrar só terra)
    """
    if landmask_vals is None:
        return vals
    if landmask_vals.shape[0] != vals.shape[0]:
        print("[AVISO] landmask e campo têm tamanhos diferentes. Máscara ignorada.")
        return vals

    if mode == "land":   # mascarar terra
        return np.where(landmask_vals >= 0.5, np.nan, vals)
    if mode == "ocean":  # mascarar oceano
        return np.where(landmask_vals < 0.5, np.nan, vals)
    return vals


# ==============================================================
# INTERPOLAÇÃO PARA GRADE REGULAR
# ==============================================================

def _interp_to_regular_grid(lon, lat, vals, res):
    """
    Interpola MPAS (pontos irregulares) para grade regular lat/lon via IDW (k=8).
    """
    if not SCIPY_OK:
        print("[AVISO] scipy não disponível — ignorando --interp.")
        return None, None, None

    # Grade alvo
    lons = np.arange(-180, 180 + res, res)
    lats = np.arange(-90, 90 + res, res)
    Lon2D, Lat2D = np.meshgrid(lons, lats)

    # pontos fonte em coord. 3D unitária
    lonr = np.deg2rad(lon)
    latr = np.deg2rad(lat)
    x = np.cos(latr) * np.cos(lonr)
    y = np.cos(latr) * np.sin(lonr)
    z = np.sin(latr)

    tree = cKDTree(np.column_stack([x, y, z]))

    # pontos alvo
    lonG = np.deg2rad(Lon2D.ravel())
    latG = np.deg2rad(Lat2D.ravel())
    xg = np.cos(latG) * np.cos(lonG)
    yg = np.cos(latG) * np.sin(lonG)
    zg = np.sin(latG)

    dist, idx = tree.query(np.column_stack([xg, yg, zg]), k=8)
    dist = np.where(dist == 0, 1e-12, dist)

    # IDW
    w = 1.0 / dist**2
    wsum = np.sum(w, axis=1)
    v_neighbors = vals[idx]
    grid_vals = np.sum(w * v_neighbors, axis=1) / wsum
    grid_vals = grid_vals.reshape(Lon2D.shape)

    return Lon2D, Lat2D, grid_vals


# ==============================================================
# PLOTAGEM / SALVAMENTO
# ==============================================================

def _make_plot(lon_deg,
               lat_deg,
               vals,
               da,
               lon_reg=None,
               lat_reg=None,
               vals_reg=None,
               extent=None,
               save_png=False,
               outdir=None,
               nivel=None,
               nivelhPa=None,
               units_label="unidade",
               vmin=None,
               vmax=None,
               cmap="jet",
               titulo=None):
    """
    Gera a figura (mostra e opcionalmente salva PNG).
    """
    var_name = da.name
    stamp_date = da.attrs.get("stamp_date", "sem_tempo")
    stamp_hm   = da.attrs.get("stamp_hm",   "sem_tempo")
    long_name  = titulo or da.attrs.get("long_name", var_name)

    fig = plt.figure(figsize=(12, 8))
    ax  = plt.axes(projection=ccrs.PlateCarree())

    if extent:
        latmin, latmax, lonmin, lonmax = extent
        ax.set_extent([lonmin, lonmax, latmin, latmax])
    else:
        ax.set_global()

    ax.coastlines(resolution="50m", linewidth=0.8)
    ax.add_feature(cfeature.BORDERS, linewidth=0.4)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, alpha=0.5)
    gl.top_labels   = False
    gl.right_labels = False

    if vals_reg is not None:
        img = ax.pcolormesh(
            lon_reg, lat_reg, vals_reg,
            shading="auto",
            cmap=cmap,
            vmin=vmin, vmax=vmax
        )
        modo = "Interpolado lat/lon"
    else:
        img = ax.scatter(
            lon_deg, lat_deg,
            c=vals,
            s=1,
            cmap=cmap,
            vmin=vmin, vmax=vmax
        )
        modo = "Grid MPAS nativo"

    # texto do nível
    if (nivelhPa is not None) and (nivel is not None):
        lvl_txt = f"{nivelhPa} hPa (idx {nivel})"
    elif nivelhPa is not None:
        lvl_txt = f"{nivelhPa} hPa"
    elif nivel is not None:
        lvl_txt = f"idx {nivel}"
    else:
        lvl_txt = ""

    # timestamp legível
    time_txt = f"{stamp_date} {stamp_hm}Z" if stamp_date != "sem_tempo" else ""

    ax.set_title(f"{long_name} {lvl_txt}\n{modo} {time_txt}", fontsize=14)

    cb = plt.colorbar(img, ax=ax, orientation="horizontal", pad=0.04)
    cb.set_label(f"{long_name} [{units_label}]")

    plt.tight_layout()



    # ========================================
    # Salvar figura (se solicitado)
    # ========================================
    if save_png:
        if (nivelhPa is not None) and (nivel is not None):
            lvl_tag = f"{int(nivelhPa)}hPa_idx{nivel}"
        elif nivelhPa is not None:
            lvl_tag = f"{int(nivelhPa)}hPa"
        elif nivel is not None:
            lvl_tag = f"nivel{nivel}"
        else:
            lvl_tag = "nivelNA"

        Path(outdir or ".").mkdir(parents=True, exist_ok=True)
        out_name = f"{var_name}_{lvl_tag}_{stamp_date}_{stamp_hm}.png"
        out_path = Path(outdir or ".") / out_name

        plt.savefig(out_path, dpi=200, bbox_inches="tight")
        print(f"[OK] Figura salva: {out_path}")

    # ========================================
    # Exibir ou fechar
    # ========================================
    if not getattr(plt, "_NO_SHOW_MODE", False):
        plt.show()
    else:
        plt.close(fig)


# ==============================================================
# PIPELINE DE UM TEMPO
# ==============================================================

def _process_single_time(
    ds,
    varname,
    t_idx,
    nivel,
    nivelhPa,
    tempo_cli,
    outdir,
    interp_on,
    res,
    unidade,
    vmin,
    vmax,
    cmap,
    extent,
    mask_land,
    mask_ocean,
    mask_file,
    titulo,
    save_png,
    fname_for_fallback
):
    """
    Processa UM índice de tempo t_idx: seleciona variável, aplica unidade,
    máscara, interpola (se pedido), plota e salva.
    """
    da, used_level = _select_variable_at_time(
        ds,
        varname,
        t_idx,
        nivel,
        nivelhPa,
        tempo_cli,
        fname_for_fallback
    )

    # coordenadas da malha
    if "lonCell" not in ds or "latCell" not in ds:
        print("\nERRO: Arquivo não possui lonCell/latCell. É MPAS atmosfera nativo?")
        sys.exit(1)

    lon_deg = np.rad2deg(ds["lonCell"].values)
    lat_deg = np.rad2deg(ds["latCell"].values)
    lon_deg = _lon_wrap(lon_deg)

    vals = da.values

    # conversão de unidade
    vals_conv, units_label = _convert_units(vals, da, unidade)

    # máscara terra/oceano
    landmask_vals = _load_landmask(ds, mask_file)
    if mask_land:
        vals_conv = _apply_landmask(vals_conv, landmask_vals, mode="land")
    if mask_ocean:
        vals_conv = _apply_landmask(vals_conv, landmask_vals, mode="ocean")

    # interpolação
    lon_reg = lat_reg = vals_reg = None
    if interp_on:
        lon_reg, lat_reg, vals_reg = _interp_to_regular_grid(lon_deg, lat_deg, vals_conv, res)

    # plot + salvar png
    _make_plot(
        lon_deg,
        lat_deg,
        vals_conv,
        da,
        lon_reg=lon_reg,
        lat_reg=lat_reg,
        vals_reg=vals_reg,
        extent=extent,
        save_png=save_png,
        outdir=outdir,
        nivel=used_level,
        nivelhPa=nivelhPa,
        units_label=units_label,
        vmin=vmin,
        vmax=vmax,
        cmap=cmap,
        titulo=titulo,
    )


# ==============================================================
# MAIN / CLI
# ==============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Plotador MPAS com suporte a níveis (--nivel/--nivelhPa), "
            "máscara terra/oceano (--mask-land/--mask-ocean + --mask-file), "
            "recorte (--extent), interpolação lat/lon (--interp --res), "
            "unidade (--unidade C/hPa), multi-tempo (--time-index / --all-times), "
            "saída PNG (--save --outdir), título custom (--titulo) e carimbo de tempo manual (--tempo)."
        )
    )

    parser.add_argument("file", type=str,
                        help="Arquivo NetCDF (ex: history.YYYY-MM-DD_HH.MM.SS.nc)")

    parser.add_argument("--var", required=True,
                        help="Variável alvo (ex: t2m, theta, qv, sst, ter).")

    # controle temporal
    parser.add_argument("--time-index", type=int, default=None,
                        help="Índice de tempo a plottar (0=primeiro). Ignorado se usar --all-times.")
    parser.add_argument("--all-times", action="store_true",
                        help="Se presente, gera mapas para TODOS os tempos do arquivo.")

    # controle vertical
    parser.add_argument("--nivel", type=int,
                        help="Índice vertical bruto (ex: --nivel 3).")
    parser.add_argument("--nivelhPa", type=float,
                        help="Nível alvo em hPa (ex: --nivelhPa 500). Tem prioridade sobre --nivel.")

    # aparência / física
    parser.add_argument("--unidade", type=str, default="original",
                        help="Conversão de unidade: original, C, hPa.")
    parser.add_argument("--vmin", type=float, help="Valor mínimo da barra de cores.")
    parser.add_argument("--vmax", type=float, help="Valor máximo da barra de cores.")
    parser.add_argument("--cmap", type=str, default="jet",
                        help="Colormap Matplotlib (ex: turbo_r, RdYlBu_r, viridis).")
    parser.add_argument("--titulo", type=str,
                        help="Título customizado (ex: 'T2M - MPAS - CASO SABRINA').")

    # interpolação
    parser.add_argument("--interp", action="store_true",
                        help="Interpolar para grade lat/lon regular.")
    parser.add_argument("--res", type=float, default=0.25,
                        help="Resolução em graus da grade interpolada (default 0.25).")

    # recorte espacial
    parser.add_argument("--extent", nargs=4, type=float,
                        metavar=("LATMIN", "LATMAX", "LONMIN", "LONMAX"),
                        help="Recorte espacial (ex: --extent -15 5 -75 -45).")

    # máscara
    parser.add_argument("--mask-land", action="store_true",
                        help="Mascarar terra (mostrar só oceano).")
    parser.add_argument("--mask-ocean", action="store_true",
                        help="Mascarar oceano (mostrar só terra).")
    parser.add_argument("--mask-file", type=str,
                        help="Outro NetCDF com 'landmask' (ex: x1.40962.init.nc).")

    # output
    parser.add_argument("--save", action="store_true",
                        help="Salvar PNG automaticamente.")
    parser.add_argument("--outdir", type=str,
                        help="Diretório de saída para PNGs (ex: ./FIGS).")

    # overrides manuais
    parser.add_argument("--tempo", type=str,
                        help="Força timestamp manual para TODOS os tempos (ex: 2024-05-20_00:00).")
    # Argumento opcional --no-show
    parser.add_argument("--no-show", action="store_true",
                        help="Gera as figuras e salva PNGs sem abrir janelas (modo operacional/lote).")

    args = parser.parse_args()
    
    # Ajuste global: se --no-show foi ativado
    plt._NO_SHOW_MODE = args.no_show

    # abrir dataset
    try:
        ds = xr.open_dataset(args.file, decode_coords="all")
    except Exception as e:
        print(f"\nERRO ao abrir NetCDF '{args.file}': {e}")
        sys.exit(1)

    # quantos tempos tem?
    if "Time" in ds.dims:
        n_times = ds.sizes["Time"]
    elif "Time" in ds.coords:
        n_times = ds.sizes["Time"]
    else:
        # arquivo sem dimensão Time → trata como 1 tempo só
        n_times = 1

    # decidir quais índices de tempo vamos processar
    if args.all_times:
        time_indices = list(range(n_times))
    else:
        # se usuário passou --time-index, usa ele
        if args.time_index is not None:
            if args.time_index < 0 or args.time_index >= n_times:
                print(f"\nERRO: --time-index {args.time_index} fora do range (0..{n_times-1}).")
                sys.exit(1)
            time_indices = [args.time_index]
        else:
            # default: só o tempo 0
            time_indices = [0]

    # processar cada tempo pedido
    for t_idx in time_indices:
        _process_single_time(
            ds=ds,
            varname=args.var,
            t_idx=t_idx,
            nivel=args.nivel,
            nivelhPa=args.nivelhPa,
            tempo_cli=args.tempo,
            outdir=args.outdir,
            interp_on=args.interp,
            res=args.res,
            unidade=args.unidade,
            vmin=args.vmin,
            vmax=args.vmax,
            cmap=args.cmap,
            extent=args.extent,
            mask_land=args.mask_land,
            mask_ocean=args.mask_ocean,
            mask_file=args.mask_file,
            titulo=args.titulo,
            save_png=args.save,
            fname_for_fallback=ds.encoding.get("source", None)
        )


if __name__ == "__main__":
    main()
