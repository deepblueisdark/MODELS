#!/usr/bin/env python3

"""
Script Python para processar saídas de precipitação do MPAS.

Calcula a precipitação total do período e a precipitação por passo de tempo
(diária, se a saída for diária) a partir das variáveis ACUMULATIVAS
rainc e rainnc.

Suporta duas saídas:
1. Grade Nativa MPAS (anexando variáveis de grade do arquivo --init)
2. Grade Lat/Lon Regular (interpolando os dados usando Scipy)

Requerimentos:
pip install xarray numpy scipy netcdf4
"""

import xarray as xr
import numpy as np
import glob
import argparse
import os
from scipy.interpolate import griddata

def find_grid_vars(ds_init):
    """Encontra todas as variáveis estáticas da grade no arquivo init."""
    print("Identificando variáveis da grade estática...")
    grid_vars = []
    for var_name, var in ds_init.variables.items():
        # Variáveis de grade são aquelas que não dependem da dimensão 'Time'
        if 'Time' not in var.dims and var_name not in ['rainc', 'rainnc']:
            grid_vars.append(var_name)
    print(f"Encontradas {len(grid_vars)} variáveis de grade.")
    return grid_vars

def interpolate_to_latlon(data_array, ds_init, target_lats, target_lons):
    """
    Interpola um DataArray (nativo nCells) para uma grade lat/lon regular.
    
    data_array: xarray.DataArray com dims (Time, nCells) ou (nCells)
    ds_init: xarray.Dataset do arquivo init
    target_lats: array numpy de latitudes-alvo
    target_lons: array numpy de longitudes-alvo
    """
    print(f"Iniciando interpolação para grade {len(target_lats)}x{len(target_lons)}...")

    # 1. Obter coordenadas de origem (centros de célula)
    # MPAS armazena lat/lon em RADIANOS. Devemos converter para graus.
    src_lat_rad = ds_init['latCell'].values
    src_lon_rad = ds_init['lonCell'].values
    
    src_lat = np.rad2deg(src_lat_rad)
    src_lon = np.rad2deg(src_lon_rad)
    
    # Ajustar longitudes de [0, 360] para [-180, 180] se necessário
    # (Scipy/griddata lida melhor com isso)
    src_lon[src_lon > 180] -= 360
    
    # 2. Preparar pontos de origem para griddata
    # Formato: (n_pontos, n_dimensões) -> (nCells, 2)
    source_points = np.column_stack((src_lon, src_lat))

    # 3. Preparar pontos-alvo (a grade lat/lon)
    grid_lon, grid_lat = np.meshgrid(target_lons, target_lats)
    target_points = np.column_stack((grid_lon.ravel(), grid_lat.ravel()))

    # 4. Verificar se os dados têm dimensão de tempo
    has_time_dim = 'Time' in data_array.dims
    
    if has_time_dim:
        print(f"Interpolando {len(data_array.Time)} passos de tempo...")
        output_data_list = []
        
        # Interpola cada passo de tempo individualmente
        for t_idx in range(len(data_array.Time)):
            print(f"  ...processando passo de tempo {t_idx+1}/{len(data_array.Time)}")
            values = data_array.isel(Time=t_idx).values
            
            # Realiza a interpolação (método linear é um bom padrão)
            interpolated_values = griddata(
                source_points, 
                values, 
                target_points, 
                method='linear'
            )
            
            # Remodelar de 1D para 2D (lat, lon)
            output_data_list.append(interpolated_values.reshape(grid_lon.shape))
        
        # Empilhar resultados em um array 3D (Time, lat, lon)
        final_data = np.stack(output_data_list, axis=0)
        
        # Criar o xarray.DataArray final
        interpolated_da = xr.DataArray(
            final_data,
            coords={'Time': data_array.Time, 'lat': target_lats, 'lon': target_lons},
            dims=['Time', 'lat', 'lon'],
            name=data_array.name,
            attrs=data_array.attrs
        )
        
    else:
        # Dados 2D (sem tempo), como a precipitação total do período
        print("Interpolando campo 2D (sem tempo)...")
        values = data_array.values
        interpolated_values = griddata(
            source_points, 
            values, 
            target_points, 
            method='linear'
        )
        
        final_data = interpolated_values.reshape(grid_lon.shape)
        
        # Criar o xarray.DataArray final
        interpolated_da = xr.DataArray(
            final_data,
            coords={'lat': target_lats, 'lon': target_lons},
            dims=['lat', 'lon'],
            name=data_array.name,
            attrs=data_array.attrs
        )
        
    print("Interpolação concluída.")
    return interpolated_da


def main():
    # --- 1. Configurar o Parser de Argumentos de Linha de Comando ---
    parser = argparse.ArgumentParser(description="Processa precipitação acumulada do MPAS.")
    
    parser.add_argument('--init', type=str, required=True,
                        help="Caminho para o arquivo init (ex: init.nc) para definições de grade.")
    
    parser.add_argument('--input', type=str, required=True,
                        help="Padrão de glob para os arquivos de dados (ex: 'history.atmosphere.*.nc')")
    
    parser.add_argument('--output_dir', type=str, default='.',
                        help="Diretório para salvar os arquivos NetCDF gerados.")

    # Argumentos de Tempo (Opcionais)
    parser.add_argument('--start_time', type=str, default=None,
                        help="Tempo inicial (formato 'YYYY-MM-DDTHH:MM:SS')")
    parser.add_argument('--end_time', type=str, default=None,
                        help="Tempo final (formato 'YYYY-MM-DDTHH:MM:SS')")

    # Argumentos de Interpolação (Opcionais)
    parser.add_argument('--interp', action='store_true',
                        help="Ativa a interpolação para grade lat/lon. (Padrão: Salvar na grade nativa)")
    
    parser.add_argument('--res', type=float, default=0.5,
                        help="Resolução em graus para interpolação (ex: 0.5)")
    
    parser.add_argument('--domain', type=float, nargs=4, default=[-90, 90, -180, 180],
                        metavar=('LAT_MIN', 'LAT_MAX', 'LON_MIN', 'LON_MAX'),
                        help="Domínio para interpolação [lat_min lat_max lon_min lon_max]")

    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)

    # --- 2. Carregar Dados ---
    print(f"Carregando arquivo init: {args.init}")
    ds_init = xr.open_dataset(args.init)
    
    data_files = sorted(glob.glob(args.input))
    if not data_files:
        print(f"Erro: Nenhum arquivo encontrado com o padrão: {args.input}")
        return
        
    print(f"Carregando {len(data_files)} arquivos de dados (ex: {data_files[0]})...")
    # xr.open_mfdataset abre todos os arquivos como um único dataset
    ds_data = xr.open_mfdataset(data_files, combine='by_coords')

    # --- 3. Selecionar Período de Tempo ---
    if args.start_time or args.end_time:
        print(f"Selecionando período de {args.start_time} a {args.end_time}")
        ds_data = ds_data.sel(Time=slice(args.start_time, args.end_time))
    else:
        print("Usando todos os passos de tempo disponíveis.")

    # --- 4. Calcular Precipitação Acumulada Total (rainc + rainnc) ---
    print("Calculando soma de rainc + rainnc...")
    # Isso mantém as dimensões (Time, nCells)
    total_accum = ds_data['rainc'] + ds_data['rainnc']
    total_accum.attrs['long_name'] = 'Total Accumulated Precipitation (rainc + rainnc)'
    total_accum.attrs['units'] = ds_data['rainc'].attrs.get('units', 'mm')

    # --- 5. Gerar Mapas (Cálculos) ---

    # MAPA TIPO 1: Chuva Total do Período
    # (Acumulado no último passo) - (Acumulado no primeiro passo)
    print("Calculando Chuva Total do Período...")
    precip_total_period = total_accum.isel(Time=-1) - total_accum.isel(Time=0)
    precip_total_period.name = 'precip_total_period'
    precip_total_period.attrs['long_name'] = 'Total precipitation over the selected period'
    # Esta variável tem dimensão (nCells)

    # MAPA TIPO 2: Chuva Diária (ou por passo de tempo)
    # (Acumulado T) - (Acumulado T-1)
    print("Calculando Chuva por Passo de Tempo (Diária)...")
    # .diff() calcula a diferença ao longo da dimensão 'Time'
    precip_daily = total_accum.diff(dim='Time')
    precip_daily.name = 'precip_per_timestep'
    precip_daily.attrs['long_name'] = 'Precipitation per model output timestep (des-acumulada)'
    # Esta variável tem dimensão (Time, nCells), mas com um passo de tempo a menos
    
    # --- 6. Salvar Saídas (Nativa ou Interpolada) ---

    if args.interp:
        # --- CAMINHO DA INTERPOLAÇÃO ---
        print("\nModo de Interpolação Ativado.")
        
        # 6a. Definir grade alvo
        lat_min, lat_max, lon_min, lon_max = args.domain
        target_lats = np.arange(lat_min, lat_max + args.res, args.res)
        target_lons = np.arange(lon_min, lon_max + args.res, args.res)

        # 6b. Interpolar Mapa Total do Período
        da_total_interp = interpolate_to_latlon(
            precip_total_period, ds_init, target_lats, target_lons
        )
        
        # 6c. Interpolar Mapa Diário
        da_daily_interp = interpolate_to_latlon(
            precip_daily, ds_init, target_lats, target_lons
        )
        
        # 6d. Salvar arquivos
        out_total_file = os.path.join(args.output_dir, f'precip_total_period_interp_{args.res}deg.nc')
        out_daily_file = os.path.join(args.output_dir, f'precip_daily_interp_{args.res}deg.nc')
        
        print(f"Salvando precipitação total (interpolada) em: {out_total_file}")
        da_total_interp.to_netcdf(out_total_file)
        
        print(f"Salvando precipitação diária (interpolada) em: {out_daily_file}")
        da_daily_interp.to_netcdf(out_daily_file)

    else:
        # --- CAMINHO NATIVO ---
        print("\nModo de Grade Nativa Ativado.")
        
        # 6a. Obter variáveis de grade do arquivo init
        grid_var_names = find_grid_vars(ds_init)
        ds_grid = ds_init[grid_var_names]
        
        # 6b. Criar Datasets de saída e anexar a grade
        ds_out_total = xr.merge([precip_total_period.to_dataset(), ds_grid])
        ds_out_daily = xr.merge([precip_daily.to_dataset(), ds_grid])
        
        # 6c. Salvar arquivos
        out_total_file = os.path.join(args.output_dir, 'precip_total_period_native.nc')
        out_daily_file = os.path.join(args.output_dir, 'precip_daily_native.nc')
        
        print(f"Salvando precipitação total (nativa) em: {out_total_file}")
        ds_out_total.to_netcdf(out_total_file)
        
        print(f"Salvando precipitação diária (nativa) em: {out_daily_file}")
        ds_out_daily.to_netcdf(out_daily_file)

    print("\nProcessamento concluído com sucesso.")

if __name__ == "__main__":
    main()