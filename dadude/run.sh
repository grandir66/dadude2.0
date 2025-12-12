#!/bin/bash
# DaDude - Script di avvio
# Avvia l'applicazione in modalità sviluppo

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════╗"
echo "║         DaDude - The Dude Connector        ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

# Directory base
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Crea .env se non esiste
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  File .env non trovato, copio da .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   Modifica .env con le tue configurazioni!${NC}"
fi

# Crea directory necessarie
mkdir -p data logs

# Carica variabili ambiente
set -a
source .env
set +a

# Determina comando pip
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo -e "${RED}❌ pip non trovato. Installa Python 3 con pip.${NC}"
    exit 1
fi

# Determina comando python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python non trovato.${NC}"
    exit 1
fi

# Ferma eventuali processi esistenti
echo -e "${YELLOW}🔍 Verifico processi DaDude in esecuzione...${NC}"
EXISTING_PIDS=$(ps aux | grep -E "(uvicorn|python.*app\.main)" | grep -v grep | awk '{print $2}')
if [ -n "$EXISTING_PIDS" ]; then
    echo -e "${YELLOW}⚠️  Trovati processi DaDude in esecuzione: $EXISTING_PIDS${NC}"
    echo -e "${YELLOW}   Termino i processi esistenti...${NC}"
    for PID in $EXISTING_PIDS; do
        kill $PID 2>/dev/null && echo -e "${GREEN}   ✓ Processo $PID terminato${NC}" || echo -e "${RED}   ✗ Impossibile terminare processo $PID${NC}"
    done
    sleep 2
else
    echo -e "${GREEN}✓ Nessun processo DaDude in esecuzione${NC}"
fi

# Verifica dipendenze
echo -e "${GREEN}📦 Verifico dipendenze...${NC}"
$PIP_CMD install -q -r requirements.txt 2>/dev/null || {
    echo -e "${YELLOW}⚠️  Provo installazione con --user...${NC}"
    $PIP_CMD install --user -q -r requirements.txt || {
        echo -e "${RED}❌ Errore installazione dipendenze${NC}"
        echo -e "${YELLOW}Prova manualmente: $PIP_CMD install -r requirements.txt${NC}"
        exit 1
    }
}

echo -e "${GREEN}✅ Dipendenze OK${NC}"

# Avvia
echo -e "${GREEN}🚀 Avvio DaDude su http://0.0.0.0:${DADUDE_PORT:-8000}${NC}"
echo -e "${GREEN}📖 Dashboard: http://localhost:${DADUDE_PORT:-8000}${NC}"
echo -e "${GREEN}📖 API Docs: http://localhost:${DADUDE_PORT:-8000}/docs${NC}"
echo ""

$PYTHON_CMD -m uvicorn app.main:app \
    --host "${DADUDE_HOST:-0.0.0.0}" \
    --port "${DADUDE_PORT:-8000}" \
    --reload
