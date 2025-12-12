#!/bin/bash
# DaDude - Script di stop
# Ferma tutti i processi DaDude in esecuzione

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}"
echo "╔════════════════════════════════════════════╗"
echo "║      DaDude - Stop Service                 ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

# Trova processi DaDude
EXISTING_PIDS=$(ps aux | grep -E "(uvicorn|python.*app\.main)" | grep -v grep | awk '{print $2}')

if [ -z "$EXISTING_PIDS" ]; then
    echo -e "${GREEN}✓ Nessun processo DaDude in esecuzione${NC}"
    exit 0
fi

echo -e "${YELLOW}🔍 Processi DaDude trovati:${NC}"
ps aux | grep -E "(uvicorn|python.*app\.main)" | grep -v grep

echo ""
echo -e "${YELLOW}⚠️  Termino i processi: $EXISTING_PIDS${NC}"

for PID in $EXISTING_PIDS; do
    if kill $PID 2>/dev/null; then
        echo -e "${GREEN}   ✓ Processo $PID terminato${NC}"
    else
        echo -e "${RED}   ✗ Impossibile terminare processo $PID (prova con sudo)${NC}"
    fi
done

sleep 1

# Verifica che siano stati terminati
REMAINING_PIDS=$(ps aux | grep -E "(uvicorn|python.*app\.main)" | grep -v grep | awk '{print $2}')
if [ -z "$REMAINING_PIDS" ]; then
    echo ""
    echo -e "${GREEN}✅ Tutti i processi DaDude sono stati fermati${NC}"
else
    echo ""
    echo -e "${RED}⚠️  Alcuni processi sono ancora in esecuzione: $REMAINING_PIDS${NC}"
    echo -e "${YELLOW}   Usa 'kill -9 $REMAINING_PIDS' per forzare la terminazione${NC}"
    exit 1
fi
