import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import numpy as np
import argparse
import sys
import os
import matplotlib

# --- Configuração do Colormap ---
cmap_name = "turbo" 
try:
    ncl_cmap = matplotlib.colormaps[cmap_name]
except KeyError:
    print(f"Colormap '{cmap_name}' não encontrado. Usando 'viridis' como fallback.")
    ncl_cmap = matplotlib.colormaps['viridis']

cmap_diff = matplotlib.colormaps['RdBu_r'] 

def plot_sst(ax, lonCell, latCell, data, levels, cmap, vmin, vmax, title_suffix, zorder=1):
    """Função auxiliar para plotar dados, usando tripcolor para evitar erros de topologia."""
    
    plot = ax.tripcolor(lonCell, latCell, data,
                          cmap=cmap,
                          vmin=vmin, vmax=vmax,
                          transform=ccrs.PlateCarree(),
                          zorder=zorder)
    
    ax.set_extent([-180, 180, -90, 90], crs=ccrs.PlateCarree())
    
    ax.add_feature(cfeature.LAND, facecolor='0.8', zorder=2) 
    ax.add_feature(cfeature.COASTLINE, facecolor='none', edgecolor='black', zorder=3) 
    
    ax.gridlines(draw_labels=True, linestyle='--', color='lightgrey', zorder=5)
    ax.set_title(f"{title_suffix}", fontsize=10)
    return plot

def main(sst_file, mesh_file, time_range):
    
    # ... (Inicialização e carregamento de arquivos - IDÊNTICO) ...
    cenLat = 0.0
    cenLon = 0.0
    r2d = 57.2957795

    try:
        f = xr.open_dataset(sst_file)
        g = xr.open_dataset(mesh_file, decode_times=False)
    except Exception as e:
        print(f"Erro ao abrir arquivos: {e}")
        sys.exit(1)

    lonCell = g['lonCell'].values * r2d
    latCell = g['latCell'].values * r2d
    
    # Determinar dimensão de tempo e limites
    time_dim_name = None
    if 'xtime' in f['sst'].dims: time_dim_name = 'xtime'
    else:
        possible_time_dims = [dim for dim in f['sst'].dims if dim.lower() != 'ncells']
        if possible_time_dims: time_dim_name = possible_time_dims[0]
    
    if not time_dim_name:
        print("Erro: Não foi possível identificar a dimensão de tempo.")
        sys.exit(1)

    num_times = f['sst'].sizes[time_dim_name]

    # Processar time_range
    if time_range:
        if len(time_range) == 1: start_time, end_time = time_range[0], time_range[0]
        elif len(time_range) == 2: start_time, end_time = time_range[0], time_range[1]
        else:
            print("Erro: O argumento --time deve ter 1 ou 2 valores.")
            sys.exit(1)
    else:
        start_time, end_time = 0, num_times - 1

    start_time = max(0, min(start_time, num_times - 1))
    end_time = max(0, min(end_time, num_times - 1))
    T_ref_idx = start_time 
    
    # --- CARREGAR DADOS E CALCULAR ESCALAS GLOBAIS ---
    print("Carregando dados e calculando escalas globais...")
    
    indices_to_load = sorted(list(set(list(range(start_time, end_time + 2))))) 
    indices_to_load = [idx for idx in indices_to_load if idx < num_times]
    
    all_sst_data = {} 
    for time_idx in indices_to_load:
        try:
            all_sst_data[time_idx] = f['sst'].isel({time_dim_name: time_idx}).values
        except Exception:
            pass
            
    if not all_sst_data or T_ref_idx not in all_sst_data:
        print("Erro: Dados insuficientes carregados.")
        return

    # 1. Escala SST (Painel 1)
    global_data_sst = np.concatenate([d[~np.isnan(d)] for d in all_sst_data.values()])
    vmin_sst = np.min(global_data_sst)
    vmax_sst = np.max(global_data_sst)
    sst_levels = np.linspace(vmin_sst, vmax_sst, 50)
    
    # 2. Escala de Diferença (Para P2 e P3)
    max_abs_diff = 0
    for i in range(start_time, end_time + 1):
        if i in all_sst_data and T_ref_idx in all_sst_data:
            # Diferença P2: T_i - T_ref
            diff2 = all_sst_data[i] - all_sst_data[T_ref_idx]
            valid_diff = diff2[~np.isnan(diff2)]
            if valid_diff.size > 0:
                max_abs_diff = max(max_abs_diff, np.max(np.abs(valid_diff)))

            # Diferença P3: T_i - T_{i+1}
            if (i + 1) in all_sst_data:
                diff3 = all_sst_data[i] - all_sst_data[i + 1]
                valid_diff = diff3[~np.isnan(diff3)]
                if valid_diff.size > 0:
                    max_abs_diff = max(max_abs_diff, np.max(np.abs(valid_diff)))

    diff_levels = np.linspace(-max_abs_diff, max_abs_diff, 51) 
    
    # --- Preparação para Plotagem ---
    output_dir = "sst_panels_2x2_fixed"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Os painéis serão salvos no diretório: {output_dir}")
    
    # --- Loop Principal: Um painel para CADA tempo Ti no intervalo ---
    for i in range(start_time, end_time + 1): 
        
        if i not in all_sst_data or T_ref_idx not in all_sst_data:
            continue
            
        T_i_data = all_sst_data[i]
        T_ref_data = all_sst_data[T_ref_idx]
        
        # P2: T_i - T_ref
        D2 = T_i_data - T_ref_data 
        
        # P3: T_i - T_{i+1}
        D3 = np.full_like(T_i_data, np.nan) 
        title_suffix_3 = f"({i} - N/A)"
        if (i + 1) in all_sst_data:
            T_i_plus_1_data = all_sst_data[i + 1]
            D3 = T_i_data - T_i_plus_1_data
            title_suffix_3 = f"({i} - {i+1})"
        
        # --- Gerar Título de Tempo ---
        filename_base = f"SST_i{i:04d}"
        
        # --- Configuração do Painel (2 LINHAS x 2 COLUNAS) ---
        fig = plt.figure(figsize=(14, 10)) # Aumentado em altura para acomodar 2 linhas
        gs = gridspec.GridSpec(2, 2, figure=fig, height_ratios=[1, 1], hspace=0.3, wspace=0.2) 

        # --- PLOT 1: Imagem Atual (Ti) ---
        ax1 = fig.add_subplot(gs[0, :], projection=ccrs.PlateCarree()) # Ocupa toda a primeira linha
        plot1 = plot_sst(ax1, lonCell, latCell, T_i_data, sst_levels, ncl_cmap, vmin_sst, vmax_sst, 
                         f"P1: SST (i={i})")
        
        # --- PLOT 2: Diferença em relação a T_ref (Ti - T_ref) ---
        ax2 = fig.add_subplot(gs[1, 0], projection=ccrs.PlateCarree())
        plot2 = plot_sst(ax2, lonCell, latCell, D2, diff_levels, cmap_diff, -max_abs_diff, max_abs_diff, 
                         f"P2: Anomalia ({i} - {T_ref_idx})")
        
        # --- PLOT 3: Diferença Sequencial (Ti - T_{i+1}) ---
        ax3 = fig.add_subplot(gs[1, 1], projection=ccrs.PlateCarree())
        
        if np.all(np.isnan(D3)):
            plot3 = plot_sst(ax3, lonCell, latCell, T_i_data, sst_levels, ncl_cmap, vmin_sst, vmax_sst, 
                             f"P3: Último ponto ({i})")
            plot_ref_for_cbar = plot1
        else:
            plot3 = plot_sst(ax3, lonCell, latCell, D3, diff_levels, cmap_diff, -max_abs_diff, max_abs_diff, 
                             f"P3: Diferença ({title_suffix_3})")
            plot_ref_for_cbar = plot3


        # --- Barras de Cor (Ajustadas para 2 Linhas) ---
        
        # Barra de cor para SST (Painel 1) - Posicionada à direita do topo
        cax_sst = fig.add_axes([0.92, 0.58, 0.02, 0.35]) 
        fig.colorbar(plot1, cax=cax_sst)
        cax_sst.set_ylabel('SST (P1)')
        
        # Barra de cor para Diferenças (Painéis 2 e 3) - Posicionada à direita da linha inferior
        cax_diff = fig.add_axes([0.92, 0.15, 0.02, 0.35])
        fig.colorbar(plot_ref_for_cbar, cax=cax_diff, ticks=[-max_abs_diff, 0, max_abs_diff])
        cax_diff.set_ylabel('Diferença (P2, P3)')


        fig.suptitle(f"SST e Anomalias no Tempo i={i} (Ref: i={T_ref_idx})", fontsize=16)
        
        output_filename = os.path.join(output_dir, f"{filename_base}.Painel_Layout_Correto.png")
        plt.savefig(output_filename, dpi=200, bbox_inches='tight')
        print(f"Painel salvo em: {output_filename}")
        plt.close(fig) 

# 4. Bloco principal que executa o script
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="Plota painéis com layout: (1) SST (topo, largura total), (2) Anomalia vs T_ref (inferior esq), (3) Anomalia sequencial (inferior dir).",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--sst', type=str, required=True, help="Caminho para o arquivo NetCDF de SST.")
    parser.add_argument('--mesh', type=str, required=True, help="Caminho para o arquivo NetCDF de malha/estático.")
    parser.add_argument(
        '--time',
        type=int,
        nargs='*', 
        help="Índices de tempo a processar. O primeiro valor é o T_ref absoluto. Ex: --time 0 30."
    )
    
    args = parser.parse_args()
    
    main(args.sst, args.mesh, args.time)