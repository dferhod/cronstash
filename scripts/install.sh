#!/bin/bash
# ==============================================================================
# Cronstash - Script d'installation automatisé pour Debian 13 (Trixie)
# ==============================================================================
set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${CYAN}             🛡️  CRONSTASH - INSTALLATION SYSTEME (DEBIAN 13)                 ${NC}"
echo -e "${BLUE}==============================================================================${NC}"

# 1. Vérification des privilèges Root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERREUR] Ce script doit être exécuté en tant que root (ou via sudo).${NC}"
  exit 1
fi

APP_DIR="/opt/cronstash"
DATA_DIR="/var/lib/cronstash"
BACKUP_DIR="/backup/cronstash"
LOG_DIR="/var/log/cronstash"
CRON_FILE="/etc/cron.d/cronstash"
NGINX_CONF_DEST="/etc/nginx/sites-available/cronstash"
SYSTEMD_SERVICE_DEST="/etc/systemd/system/cronstash.service"

DEFAULT_ADMIN_USER="admin"
DEFAULT_ADMIN_PASS="${CRONSTASH_ADMIN_PASS:-Cronstash2026!Secure}"

# 2. Mise à jour système et installation des prérequis
echo -e "\n${YELLOW}[1/8] Mise à jour des paquets et installation des dépendances...${NC}"
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 \
  python3-venv \
  python3-pip \
  curl \
  wget \
  ca-certificates \
  gnupg \
  lsb-release \
  gzip \
  cron \
  nginx

# 3. Dépôt officiel PostgreSQL pour PostgreSQL 18
echo -e "\n${YELLOW}[2/8] Configuration du client PostgreSQL 18...${NC}"
install -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/postgresql.gpg ]; then
  curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg
fi

DEBIAN_CODENAME=$(lsb_release -cs)
echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt ${DEBIAN_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list

apt-get update -y
if apt-cache show postgresql-client-18 >/dev/null 2>&1; then
  apt-get install -y postgresql-client-18
else
  echo -e "${YELLOW}Paquet postgresql-client-18 non trouvé, installation du client par défaut...${NC}"
  apt-get install -y postgresql-client
fi

# 4. Création des répertoires système
echo -e "\n${YELLOW}[3/8] Création de l'arborescence système et des permissions...${NC}"
mkdir -p "${APP_DIR}"
mkdir -p "${DATA_DIR}"
mkdir -p "${BACKUP_DIR}/pgsql"
mkdir -p "${BACKUP_DIR}/rdf4j"
mkdir -p "${LOG_DIR}"

chmod 750 "${DATA_DIR}"
chmod 755 "${BACKUP_DIR}"
chmod 755 "${BACKUP_DIR}/pgsql"
chmod 755 "${BACKUP_DIR}/rdf4j"
chmod 755 "${LOG_DIR}"

# 5. Déploiement des fichiers d'application
echo -e "\n${YELLOW}[4/8] Déploiement des fichiers du projet dans ${APP_DIR}...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
  cp -r "${SCRIPT_DIR}/backend" "${APP_DIR}/"
  cp -r "${SCRIPT_DIR}/scripts" "${APP_DIR}/"
  cp -r "${SCRIPT_DIR}/config" "${APP_DIR}/"
  cp "${SCRIPT_DIR}/cli.py" "${APP_DIR}/cli.py" 2>/dev/null || true
  if [ -d "${SCRIPT_DIR}/frontend" ]; then
    cp -r "${SCRIPT_DIR}/frontend" "${APP_DIR}/"
  fi
fi

# S'assurer que cli.py est executable
chmod +x "${APP_DIR}/cli.py"
chmod +x "${APP_DIR}/backend/cli.py"

# 6. Création de l'environnement virtuel Python
echo -e "\n${YELLOW}[5/8] Configuration du venv Python 3.13 et installation des paquets...${NC}"
if [ ! -d "${APP_DIR}/venv" ]; then
  python3 -m venv "${APP_DIR}/venv"
fi

"${APP_DIR}/venv/bin/pip" install --upgrade pip setuptools wheel
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

# 7. Initialisation de la base SQLite et compte administrateur
echo -e "\n${YELLOW}[6/8] Initialisation de la base SQLite et du compte Administrateur...${NC}"
export CRONSTASH_DB_PATH="${DATA_DIR}/cronstash.db"
export CRONSTASH_BACKUP_PATH="${BACKUP_DIR}"
export CRONSTASH_CRON_FILE="${CRON_FILE}"

"${APP_DIR}/venv/bin/python" "${APP_DIR}/cli.py" init-admin --username "${DEFAULT_ADMIN_USER}" --password "${DEFAULT_ADMIN_PASS}"
"${APP_DIR}/venv/bin/python" "${APP_DIR}/cli.py" sync-cron

# Fixer les permissions du fichier crontab (obligatoire 0644 sur Debian)
touch "${CRON_FILE}"
chmod 644 "${CRON_FILE}"
touch "${LOG_DIR}/cron.log"
chmod 666 "${LOG_DIR}/cron.log"

# 8. Configuration Systemd
echo -e "\n${YELLOW}[7/8] Installation et démarrage du service Systemd...${NC}"
cp "${APP_DIR}/scripts/cronstash.service" "${SYSTEMD_SERVICE_DEST}"
systemctl daemon-reload
systemctl enable cronstash
systemctl restart cronstash

# 9. Configuration Nginx
echo -e "\n${YELLOW}[8/8] Configuration du serveur Web et Proxy Inverse Nginx (port 8080)...${NC}"
cp "${APP_DIR}/config/nginx.conf" "${NGINX_CONF_DEST}"
ln -sf "${NGINX_CONF_DEST}" /etc/nginx/sites-enabled/cronstash

# Test de la configuration Nginx
nginx -t
systemctl restart nginx

echo -e "\n${GREEN}==============================================================================${NC}"
echo -e "${GREEN}             ✅ INSTALLATION DE CRONSTASH TERMINÉE AVEC SUCCÈS !             ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo -e "Interface Web : ${CYAN}http://<adresse_ip_serveur>:8080${NC} ou ${CYAN}http://127.0.0.1:8080${NC}"
echo -e "Identifiants d'accès :"
echo -e "  - Utilisateur : ${YELLOW}${DEFAULT_ADMIN_USER}${NC}"
echo -e "  - Mot de passe : ${YELLOW}${DEFAULT_ADMIN_PASS}${NC}"
echo -e ""
echo -e "Emplacements système configurés :"
echo -e "  - Racine App      : ${APP_DIR}"
echo -e "  - Base de données : ${DATA_DIR}/cronstash.db"
echo -e "  - Sauvegardes PG  : ${BACKUP_DIR}/pgsql/"
echo -e "  - Sauvegardes RDF : ${BACKUP_DIR}/rdf4j/"
echo -e "  - Crontab Système : ${CRON_FILE}"
echo -e "  - Service Systemd : systemctl status cronstash"
echo -e "==============================================================================\n"
