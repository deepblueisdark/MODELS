#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grid_rotate.py — Rotaciona uma malha MPAS em torno de um novo centro geográfico.

Versão moderna e ampliada do utilitário Fortran `grid_rotate.f90` (MPAS-Tools).

Uso:
    python grid_rotate.py \
        --input x1.40962.init.nc \
        --output x1.40962_rot.nc \
        --center-lon -90 --center-lat 30 \
        --birdseye 0 --preview
"""

import numpy as np
import xarray as xr
import math
import argparse
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# --------------------------------------------------------
# Funções auxiliares matemáticas
# --------------------------------------------------------
def sph_to_cart(lon, lat):
    """(radianos) -> coordenadas cartesianas unitárias."""
    x = np.cos(lat) * np.cos(lon)
    y = np.cos(lat) * np.sin(lon)
    z = np.sin(lat)
    return x, y, z

def cart_to_sph(x, y, z):
    """Coordenadas cartesianas -> (lon, lat) em radianos."""
    lon = np.arctan2(y, x)
    lat = np.arcsin(z / np.sqrt(x*x + y*y + z*z))
    return lon, lat

def rotation_matrix(axis, angle):
    """Matriz de rotação em torno de um vetor unitário."""
    ux, uy, uz = axis / np.linalg.norm(axis)
    a = math.radians(angle)
    c, s = np.cos(a), np.sin(a)
    R = np.array([
        [c + ux*ux*(1-c),    ux*uy*(1-c) - uz*s, ux*uz*(1-c) + uy*s],
        [uy*ux*(1-c) + uz*s, c + uy*uy*(1-c),    uy*uz*(1-c) - ux*s],
        [uz*ux*(1-c) - uy*s, uz*uy*(1-c) + ux*s, c + uz*uz*(1-c)]
    ])
    return R

def rotate_geographically(lon, lat, center_lon, center_lat, birdseye=0.0):
    """
    Roda todos os pontos (lon, lat) para um novo centro geográfico.
    Equivale à transformação do grid_rotate.f90.
    """
    lon = np.asarray(lon)
    lat = np.asarray(lat)

    # Passo 1: converter para cartesiano
    x, y, z = sph_to_cart(lon, lat)
    v = np.array([x, y, z])

    # Vetores de referência
    # Original polo (0°, 90°N)
    xz, yz, zz = sph_to_cart(np.radians(0), np.radians(90))
    # Novo polo
    xn, yn, zn = sph_to_cart(np.radians(center_lon), np.radians(center_lat))

    # Eixo de rotação entre polos
    axis = np.cross([xz, yz, zz], [xn, yn, zn])
    if np.linalg.norm(axis) < 1e-12:
        axis = np.array([0, 0, 1])

    # Ângulo entre polos
    angle = np.degrees(np.arccos(np.clip(np.dot([xz, yz, zz], [xn, yn, zn]), -1, 1)))
    R = rotation_matrix(axis, angle)

    # Aplicar rotação para mover o polo
    v_rot = np.tensordot(R, v, axes=([1, 0]))

    # Birdseye rotation (rotação local ao redor do novo centro)
    if abs(birdseye) > 1e-8:
        Rb = rotation_matrix([xn, yn, zn], birdseye)
        v_rot = np.tensordot(Rb, v_rot, axes=([1, 0]))

    x2, y2, z2 = v_rot
    lon2, lat2 = cart_to_sph(x2, y2, z2)
    return ((lon2 + np.pi) % (2*np.pi)) - np.pi, lat2

# --------------------------------------------------------
# Visualização
# --------------------------------------------------------
def plot_mesh_comparison(ds_before, ds_after, title_before="Original", title_after="Rotacionado"):
    """Mostra comparação lado a lado."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), subplot_kw={"projection": ccrs.PlateCarree()})
    for ax, ds, title in zip(axes, [ds_before, ds_after], [title_before, title_after]):
        ax.set_global()
        ax.coastlines(linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linewidth=0.3)
        ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5)
        ax.scatter(np.degrees(ds["lonCell"]), np.degrees(ds["latCell"]),
                   s=1, c='blue', alpha=0.5, transform=ccrs.PlateCarree())
        ax.set_title(title, fontsize=11)
    plt.suptitle("Comparação da Malha MPAS (Antes e Depois da Rotação)", fontsize=13, weight="bold")
    plt.tight_layout()
    plt.show()

# --------------------------------------------------------
# Função principal
# --------------------------------------------------------
def rotate_grid(input_file, output_file, center_lon, center_lat, birdseye=0.0, preview=False):
    print(f"[*] Lendo malha: {input_file}")
    ds = xr.open_dataset(input_file)
    ds_before = ds.copy() if preview else None

    print(f"[*] Centralizando malha em ({center_lat:.2f}°, {center_lon:.2f}°) com birdseye={birdseye:.2f}°")
    for var_lon, var_lat in [
        ("lonCell", "latCell"),
        ("lonVertex", "latVertex"),
        ("lonEdge", "latEdge"),
    ]:
        if var_lon in ds and var_lat in ds:
            print(f"    -> Rotacionando {var_lon}/{var_lat}")
            lon, lat = ds[var_lon].values, ds[var_lat].values
            lon2, lat2 = rotate_geographically(np.degrees(lon), np.degrees(lat),
                                               center_lon, center_lat, birdseye)
            ds[var_lon].values = np.radians(lon2)
            ds[var_lat].values = lat2

    print(f"[*] Salvando arquivo rotacionado: {output_file}")
    ds.to_netcdf(output_file, mode="w")
    print("[✓] Concluído com sucesso.")

    if preview and ds_before is not None:
        plot_mesh_comparison(ds_before, ds)

# --------------------------------------------------------
# CLI
# --------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rotaciona uma malha MPAS para um novo centro geográfico.")
    parser.add_argument("--input", "-i", required=True, help="Arquivo NetCDF de entrada (ex: x1.40962.init.nc)")
    parser.add_argument("--output", "-o", required=True, help="Arquivo NetCDF de saída (ex: x1.40962_rot.nc)")
    parser.add_argument("--center-lon", type=float, required=True, help="Longitude do novo centro (graus)")
    parser.add_argument("--center-lat", type=float, required=True, help="Latitude do novo centro (graus)")
    parser.add_argument("--birdseye", type=float, default=0.0, help="Rotação local (graus, sentido anti-horário)")
    parser.add_argument("--preview", action="store_true", help="Mostra malha antes/depois da rotação")
    args = parser.parse_args()

    rotate_grid(args.input, args.output, args.center_lon, args.center_lat,
                birdseye=args.birdseye, preview=args.preview)
