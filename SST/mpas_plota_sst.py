import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
import argparse
import sys
import os
import matplotlib

# 1. Usar o colormap 'turbo' diretamente
# O bloco try/except para ncl_cmap foi removido, pois agora usaremos 'turbo' fixo.
print("Usando o colormap 'turbo'.")
cmap_name = "turbo" 
try:
    ncl_cmap = matplotlib.colormaps[cmap_name]
except KeyError:
    print(f"Colormap '{cmap_name}' não encontrado. Usando 'viridis' como fallback.")
    ncl_cmap = matplotlib.colormaps['viridis']


def main(sst_file, mesh_file, time_range):
    """
    Função principal para plotar os dados de SST do MPAS.
    """
    filled = True
    cenLat = 0.0
    cenLon = 0.0
    projection_name = "CylindricalEquidistant"

    r2d = 57.2957795  # radians to degrees

    try:
        f = xr.open_dataset(sst_file)
        g = xr.open_dataset(mesh_file, decode_times=False)

    except FileNotFoundError as e:
        print(f"Erro: Arquivo não encontrado.")
        print(f"Detalhe: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Erro ao abrir arquivos: {e}")
        sys.exit(1)

    lonCell = g['lonCell'].values * r2d
    latCell = g['latCell'].values * r2d

    # --- Determinar a dimensão de tempo e Limites ---
    time_dim_name = None
    try:
        if 'xtime' in f['sst'].dims:
            time_dim_name = 'xtime'
        else:
            possible_time_dims = [dim for dim in f['sst'].dims if dim.lower() != 'ncells']
            if possible_time_dims:
                time_dim_name = possible_time_dims[0]
            else:
                raise ValueError("Nenhuma dimensão de tempo identificável em 'sst'.")
    except Exception as e:
        print(f"Erro fatal ao tentar determinar a dimensão de tempo para 'sst': {e}")
        sys.exit(1)

    num_times = f['sst'].sizes[time_dim_name]

    # Processar o argumento time_range (mesma lógica de antes)
    if time_range:
        if len(time_range) == 1:
            start_time = time_range[0]
            end_time = time_range[0]
        elif len(time_range) == 2:
            start_time = time_range[0]
            end_time = time_range[1]
        else:
            print("Erro: O argumento --time deve ter 1 ou 2 valores (ex: --time 0 10 ou --time 5).")
            sys.exit(1)
    else: # Se --time não for especificado, processa todos os tempos
        start_time = 0
        end_time = num_times - 1

    start_time = max(0, min(start_time, num_times - 1))
    end_time = max(0, min(end_time, num_times - 1))

    print(f"Configurando para gerar plots para os índices de tempo de {start_time} a {end_time} (inclusive).")

    # --- CALCULAR VMIN E VMAX GERAL ---
    print("Calculando Vmin e Vmax geral para escala de cor consistente...")
    all_data = []
    for time_idx in range(start_time, end_time + 1):
        try:
            fld = f['sst'].isel({time_dim_name: time_idx}).values
            # Garantir que apenas valores não nulos sejam considerados para min/max
            valid_data = fld[~np.isnan(fld)] 
            if valid_data.size > 0:
                all_data.append(valid_data)
        except Exception:
            continue
            
    if not all_data:
        print("Erro: Nenhum dado válido encontrado nos índices de tempo selecionados.")
        sys.exit(1)

    # Concatenar todos os arrays e calcular min/max
    global_data = np.concatenate(all_data)
    vmin = np.min(global_data)
    vmax = np.max(global_data)
    print(f"Escala de cor definida: Vmin={vmin:.2f}, Vmax={vmax:.2f}")
    
    # Criar os níveis de contorno com base no vmin/vmax global
    levels = np.linspace(vmin, vmax, 50) # 50 níveis entre min e max

    # Criar um diretório para salvar as imagens
    output_dir = "sst_plots_turbo"
    os.makedirs(output_dir, exist_ok=True)
    print(f"As imagens serão salvas no diretório: {output_dir}")

    # Loop sobre os passos de tempo para plotar
    for time_idx in range(start_time, end_time + 1):
        try:
            fld = f['sst'].isel({time_dim_name: time_idx}).values
        except Exception as e:
            print(f"Erro ao ler 'sst' para o índice de tempo {time_idx}: {e}")
            continue

        # --- Configuração da Plotagem ---
        if projection_name == "CylindricalEquidistant":
            map_projection = ccrs.PlateCarree(central_longitude=cenLon)
        else:
            map_projection = ccrs.PlateCarree(central_longitude=cenLon)

        fig = plt.figure(figsize=(12, 8))
        ax = plt.axes(projection=map_projection)

        ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())

        ax.add_feature(cfeature.LAND, facecolor='0.8', zorder=1) 
        ax.add_feature(cfeature.COASTLINE, zorder=2)

        ax.gridlines(draw_labels=True, linestyle='--', color='lightgrey')

        # Obter o rótulo de tempo (mantendo a lógica anterior, focando no índice se a data falhar)
        time_label = f"Índice de Tempo: {time_idx}"
        filename_time_str = f"idx{time_idx:04d}" # Padrão de fallback
        
        try:
            if time_dim_name == 'xtime' and 'xtime' in f.coords:
                time_str = f['xtime'].isel(xtime=time_idx).values.tobytes().decode('utf-8').strip()
                time_label = f"SST ({time_str})"
                filename_time_str = time_str.replace('-', '').replace('_', '.').replace(':', '')
            elif time_dim_name in f.coords and np.issubdtype(f[time_dim_name].dtype, np.datetime64):
                time_val = f[time_dim_name].isel({time_dim_name: time_idx}).dt.strftime("%Y-%m-%d %H:%M:%S").item()
                time_label = f"SST ({time_val})"
                filename_time_str = f[time_dim_name].isel({time_dim_name: time_idx}).dt.strftime("%Y%m%d_%H%M%S").item()
        except Exception:
            pass # Mantém o fallback se houver erro

        ax.set_title(time_label)

        plot_zorder = 0 

        if filled:
            plot = ax.tricontourf(lonCell, latCell, fld,
                                  levels=levels, # Usa os níveis globais
                                  cmap=ncl_cmap, # Usa 'turbo'
                                  extend='both',
                                  transform=ccrs.PlateCarree(),
                                  zorder=plot_zorder)
            
            cbar = plt.colorbar(plot, ax=ax, orientation='vertical', shrink=0.9, pad=0.05)
            cbar.set_label('SST') # Adiciona rótulo à barra de cor
            cbar.outline.set_visible(False)

        # --- Nomenclatura do arquivo de saída (SEM "adata.") ---
        output_filename = os.path.join(output_dir, f"SST.{filename_time_str}.png")
        plt.savefig(output_filename, dpi=200, bbox_inches='tight')
        print(f"Plot salvo em: {output_filename}")
        plt.close(fig) # Fecha a figura

# 4. Bloco principal que executa o script
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="Plota dados SST do MPAS, usando o colormap 'turbo' com escala global, para múltiplos tempos.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--sst', type=str, required=True, help="Caminho para o arquivo NetCDF de SST.")
    parser.add_argument('--mesh', type=str, required=True, help="Caminho para o arquivo NetCDF de malha/estático.")
    parser.add_argument(
        '--time',
        type=int,
        nargs='*', 
        help="Índice(s) de tempo para gerar plots. Ex: --time 0 10 (intervalo) ou --time 5 (único)."
    )
    
    args = parser.parse_args()
    
    main(args.sst, args.mesh, args.time)