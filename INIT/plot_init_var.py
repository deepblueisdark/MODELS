import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import argparse
import sys

def plot_mpas_cell_data(file_path, variable_name):
    """
    Carrega o arquivo NetCDF do MPAS, extrai a variável e plota em um mapa global.
    A plotagem é feita usando a projeção de pontos (scatter),
    pois o grid é não-estruturado (nCells).
    """
    try:
        # 1. Carregar o dataset
        # Abrir o arquivo sem carregar os dados das variáveis nas dimensões maiores, por performance
        ds = xr.open_dataset(file_path, decode_coords="all")
        
    except FileNotFoundError:
        print(f"\nERRO: Arquivo não encontrado: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERRO ao ler o arquivo NetCDF: {e}")
        sys.exit(1)

    # 2. Validar e Extrair a Variável
    if variable_name not in ds.variables:
        print(f"\nERRO: Variável '{variable_name}' não encontrada no arquivo.")
        print("Variáveis disponíveis em nCells: ter, landmask, tslb, sst, t2m, etc.")
        sys.exit(1)
        
    # Variáveis Time, nCells (ex: t2m, sst, snow)
    data_var = ds[variable_name]
    
    # Garantir que a variável tem a dimensão 'Time' e 'nCells' e pegar o primeiro (e único) 'Time'
    if 'Time' in data_var.dims:
        # Se for 3D (Time, nCells, nVertLevels), pegar o primeiro nível e o primeiro Time.
        if 'nVertLevels' in data_var.dims:
            plot_data = data_var.isel(Time=0, nVertLevels=0)
            print(f"AVISO: {variable_name} é 3D. Plotando o PRIMEIRO NÍVEL VERTICAL (nVertLevels=0).")
        # Se for 2D (Time, nCells) - como t2m
        else:
            plot_data = data_var.isel(Time=0)
    else:
         # Se for 1D (nCells) - como ter ou landmask
        plot_data = data_var
        
    # 3. Preparar Coordenadas e Converter para Graus
    # As coordenadas estão em radianos, mas o Cartopy espera graus.
    lon_deg = np.rad2deg(ds['lonCell'].values)
    lat_deg = np.rad2deg(ds['latCell'].values)
    
    # Extrair os dados da variável
    plot_values = plot_data.values

    # 4. Plotagem com Cartopy
    
    # Tenta obter o nome longo e as unidades para o título/barra de cores
    long_name = plot_data.attrs.get('long_name', variable_name)
    units = plot_data.attrs.get('units', 'unidade desconhecida')

    # Configuração do Plot
    fig = plt.figure(figsize=(12, 8))
    # Usar projeção PlateCarree para um mapa Lat/Lon simples
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree()) 
    
    # Adicionar contornos de mapa
    ax.coastlines(resolution='50m')
    ax.gridlines(draw_labels=True)
    ax.set_global()
    
    # A plotagem do MPAS é feita mapeando cada célula (nCells) para um ponto (lonCell, latCell).
    # O `scatter` é usado aqui, mas para grids não-estruturados grandes, a técnica ideal
    # seria regridar para um lat/lon regular, ou usar tripcolor/pcolormesh.
    # Para uma visualização rápida e fiel no grid nativo, a plotagem de pontos é comum.
    
    # Adicionando o termo `alpha=0.5` para transparência ajuda a visualizar áreas densas.
    scatter = ax.scatter(lon_deg, lat_deg, c=plot_values,
                         cmap='jet', marker='.', s=1,
                         transform=ccrs.PlateCarree(),
                         label=f'{long_name} ({units})') 

    # Título
    ax.set_title(f'MPAS Global: {long_name} ({variable_name})', fontsize=16)

    # Barra de Cores
    cbar = plt.colorbar(scatter, ax=ax, orientation='horizontal', pad=0.05, aspect=50)
    cbar.set_label(f'{long_name} [{units}]')
    
    plt.tight_layout()
    plt.show()


# 5. Configuração do Comando de Linha
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ferramenta de plotagem de dados 2D do MPAS (Time, nCells).")
    parser.add_argument("file", type=str, help="Caminho para o arquivo NetCDF do MPAS (e.g., x1.40962.init.nc)")
    parser.add_argument("--var", type=str, required=True, 
                        help="Nome da variável a ser plotada (e.g., t2m, sst, ter).")
    
    args = parser.parse_args()
    
    # Chamada da função de plotagem com os argumentos de linha de comando
    plot_mpas_cell_data(args.file, args.var)