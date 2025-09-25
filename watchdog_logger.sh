#!/usr/bin/env bash
# ------------------------------------------------------------
# Watchdog Logger — coleta periódica de métricas p/ diagnóstico
# Requer (opcional mas recomendado): sysstat (iostat/mpstat/pidstat), iotop
# Execute como root p/ métricas completas de IO por processo.
# ------------------------------------------------------------
set -euo pipefail

# === Configurações ===
INTERVAL_SECONDS="${INTERVAL_SECONDS:-15}"     # intervalo entre coletas
LOG_DIR="${LOG_DIR:-/var/log/watchdog-logger}" # pasta de logs
MAX_LOGS="${MAX_LOGS:-5000}"                   # retenção: nº máx. de arquivos
HOSTNAME="$(hostname -s)"

mkdir -p "$LOG_DIR"

ts() { date +"%Y-%m-%d_%H-%M-%S"; }

have() { command -v "$1" >/dev/null 2>&1; }

collect_once() {
  local now f
  now="$(ts)"
  f="$LOG_DIR/${HOSTNAME}_${now}.log"

  {
    echo "=== Watchdog Logger ==="
    echo "Host: $HOSTNAME"
    echo "Data: $(date -R)"
    echo "Kernel: $(uname -srmo)"
    echo "Uptime: $(uptime -p) | Load: $(cat /proc/loadavg)"
    echo

    echo "## Memória (free -m)"
    free -m || true
    echo

    echo "## /proc/meminfo (principais)"
    egrep -i 'Mem(Total|Free|Available)|Buffers|Cached|Swap(Total|Free)|Dirty|Writeback' /proc/meminfo || true
    echo

    echo "## PSI (Pressão) — /proc/pressure"
    for r in cpu memory io; do
      echo "-- $r --"
      [ -r "/proc/pressure/$r" ] && cat "/proc/pressure/$r" || echo "N/A"
    done
    echo

    echo "## Espaço em disco (df -hT)"
    df -hT || true
    echo

    echo "## Inodes (df -i)"
    df -i || true
    echo

    echo "## Estatísticas rápidas (vmstat 1 3)"
    have vmstat && vmstat 1 3 || echo "vmstat não instalado"
    echo

    echo "## CPU (mpstat 1 3)"
    have mpstat && mpstat -P ALL 1 3 || echo "mpstat (sysstat) não instalado"
    echo

    echo "## IO de disco (iostat -xz 1 3)"
    have iostat && iostat -xz 1 3 || echo "iostat (sysstat) não instalado"
    echo

    echo "## IO por processo (pidstat -d 1 3)"
    have pidstat && pidstat -d 1 3 || echo "pidstat (sysstat) não instalado"
    echo

    echo "## IO por processo (instantâneo iotop -b -n 1)"
    if have iotop; then
      # iotop precisa de root/cap_sys_admin para info completa
      iotop -b -n 1 || true
    else
      echo "iotop não instalado"
    fi
    echo

    echo "## Top processos por memória (ps aux --sort=-rss | head)"
    ps aux --sort=-rss | head -n 30 || true
    echo

    echo "## Top processos por CPU (ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head)"
    ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 30 || true
    echo

    echo "## Handles/FDs por processo (lsof -n | wc -l) [amostra]"
    if have lsof; then
      echo "Total FDs abertos: $(lsof -n 2>/dev/null | wc -l)"
      # Top 10 por FDs
      echo "Top 10 por FDs:"
      lsof -n 2>/dev/null | awk '{print $1,$2}' | sed 1d | sort | uniq -c | sort -nr | head -n 10 || true
    else
      echo "lsof não instalado"
    fi
    echo

    echo "## Conexões e sockets (ss -s)"
    have ss && ss -s || echo "ss não disponível"
    echo

    echo "## Últimos eventos do kernel (dmesg -T | tail)"
    dmesg -T | tail -n 200 || true
    echo

    echo "## Últimos avisos/erros do systemd-journald (journalctl -p 4..0 -n 200)"
    if have journalctl; then
      journalctl -p 4..0 -n 200 --no-pager || true
    else
      echo "journalctl não disponível"
    fi
    echo

    echo "## Temperaturas (sensors) — se disponível"
    if have sensors; then
      sensors || true
    else
      echo "sensors não instalado (pacote lm-sensors)"
    fi
    echo

    echo "## SMART (saúde discos) — se disponível"
    if have smartctl; then
      for d in /dev/sd? /dev/nvme?n?; do
        [ -e "$d" ] || continue
        echo "-- $d --"
        smartctl -H "$d" 2>/dev/null || echo "sem SMART/perm."
      done
    else
      echo "smartctl não instalado (pacote smartmontools)"
    fi
    echo
  } > "$f"

  # Retenção simples: apaga logs mais antigos
  local count
  count=$(ls -1 "$LOG_DIR"/*.log 2>/dev/null | wc -l || echo 0)
  if (( count > MAX_LOGS )); then
    ls -1t "$LOG_DIR"/*.log | tail -n +"$((MAX_LOGS+1))" | xargs -r rm -f
  fi
}

echo "[Watchdog] Iniciando com intervalo = ${INTERVAL_SECONDS}s; logs em ${LOG_DIR}"
while true; do
  collect_once || echo "[Watchdog] coleta falhou em $(date -R)" >&2
  sleep "$INTERVAL_SECONDS"
done
