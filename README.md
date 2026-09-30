# 🛡️ Cronstash

> **Gestionnaire de sauvegardes automatiques pour PostgreSQL 18 et RDF4J sur Debian 13 (Trixie).**

Cronstash est une application web autonome complète, sécurisée et modulaire pour la gestion, la planification et la supervision des sauvegardes de bases de données relationnelles (PostgreSQL 18) et graphes RDF (Triplestores RDF4J).

---

## 📋 Table des Matières

1. [Fonctionnalités Clés](#-fonctionnalités-clés)
2. [Architecture du Projet](#-architecture-du-projet)
3. [Spécifications Techniques & Chemins Système](#-spécifications-techniques--chemins-système)
4. [Installation sur Debian 13 (Trixie)](#-installation-sur-debian-13-trixie)
5. [Moteur CLI & Crontab](#-moteur-cli--crontab)
6. [Algorithme de Rétention GFS](#-algorithme-de-rétention-gfs-grandfather-father-son)
7. [Système de Notifications](#-système-de-notifications)
8. [Développement Local](#-développement-local)
9. [Sécurité](#-sécurité)

---

## ✨ Fonctionnalités Clés

- **Découverte Dynamique des Bases :**
  - **PostgreSQL 18** : Interrogation automatique de `pg_database` excluant les bases modèles et système (`postgres`).
  - **RDF4J Triplestores** : Découverte via l'API REST HTTP `/repositories` avec en-têtes JSON SPARQL.
  - Sélection par cases à cocher et génération de tâches de sauvegarde en 1 clic.
- **Moteur d'Exécution Haute Performance :**
  - PostgreSQL : `pg_dump` format personnalisé compressé (`-F c -b -v`).
  - RDF4J : Streaming HTTP avec sérialisation Turtle (`Accept: application/x-turtle`) vers `gzip`.
- **Politique de Rétention GFS (Grandfather-Father-Son) :**
  - **Fils (Son / Daily)** : Maintien de $N_1$ jours de sauvegardes quotidiennes.
  - **Père (Father / Weekly)** : Maintien de $N_2$ sauvegardes hebdomadaires (dimanche).
  - **Grand-père (Grandfather / Monthly)** : Maintien de $N_3$ sauvegardes mensuelles (1er du mois).
  - Purge physique automatique des archives obsolètes après chaque exécution.
- **Synchronisation Système `/etc/cron.d/cronstash` :**
  - Écriture atomique et respect strict des permissions `0644`.
- **Double Canal d'Alertes :**
  - Courriel SMTP au format HTML structuré et responsive.
  - Webhooks Discord avec Embeds riches (vert/rouge, taille, durée, logs d'erreur).
  - Boutons de test interactifs dans l'IHM.
- **IHM Moderne Svelte 5 / SvelteKit SPA :**
  - Single Page Application compilée via `@sveltejs/adapter-static`.
  - Mode sombre épuré avec Tailwind CSS.
  - Explorateur d'archives avec téléchargement direct et déclenchement instantané.

---

## 🏛 Architecture du Projet

```text
/opt/cronstash/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints REST (auth, dashboard, servers, jobs, backups, logs, notifications)
│   │   ├── core/         # Config, securite Argon2id/JWT, base SQLite asynchrone
│   │   ├── models/       # Modeles SQLAlchemy 2.0 (User, Server, Job, BackupLog, NotificationConfig)
│   │   ├── schemas/      # Schemas Pydantic v2
│   │   ├── services/     # Connecteurs PG/RDF4J, moteur GFS, notifications SMTP/Discord, cron_service
│   │   └── main.py       # Point d'entree FastAPI avec montage SPA statique
│   ├── cli.py            # Point d'entree pour l'execution automatique par cron
│   ├── requirements.txt  # Dependances Python 3.13
│   └── tests/            # Tests d'integration API et unitaires GFS
├── frontend/             # SPA SvelteKit (Svelte 5 + Tailwind CSS + adapter-static)
│   ├── src/
│   │   ├── lib/          # Client API, store toasts et gestion d'etat
│   │   └── routes/       # Pages : /dashboard, /servers, /jobs, /backups, /notifications, /login
│   ├── svelte.config.js  # Configure avec adapter-static (fallback: 'index.html')
│   ├── vite.config.js    # Proxy API de developpement
│   └── package.json
├── scripts/
│   ├── install.sh        # Script d'installation systeme automatisé Debian 13
│   └── cronstash.service # Unite Systemd pour Uvicorn
└── config/
    └── nginx.conf        # Proxy inverse Nginx sur port 8080
```

---

## ⚙️ Spécifications Techniques & Chemins Système

| Rôle | Chemin Système (Debian 13) |
|---|---|
| **Racine Application** | `/opt/cronstash/` |
| **Base de Données SQLite** | `/var/lib/cronstash/cronstash.db` |
| **Sauvegardes PostgreSQL** | `/backup/cronstash/pgsql/<server_name>/` |
| **Sauvegardes RDF4J** | `/backup/cronstash/rdf4j/<server_name>/` |
| **Fichier Crontab** | `/etc/cron.d/cronstash` |
| **Journal Cron** | `/var/log/cronstash/cron.log` |
| **Service Systemd** | `/etc/systemd/system/cronstash.service` |
| **Port Proxy Nginx** | `http://127.0.0.1:8080` |
| **Port Backend Uvicorn** | `http://127.0.0.1:8000` |

---

## 🚀 Installation sur Debian 13 (Trixie)

Exécutez le script d'installation en tant que `root` :

```bash
git clone https://github.com/votre-compte/cronstash.git /opt/cronstash
cd /opt/cronstash
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

Le script effectue automatiquement :
1. L'installation des paquets APT : `python3`, `python3-venv`, `postgresql-client-18`, `curl`, `gzip`, `nginx`, `cron`.
2. La création de l'arborescence `/backup/cronstash/`, `/var/lib/cronstash/` et `/var/log/cronstash/`.
3. La création de l'environnement virtuel Python et l'installation des dépendances.
4. L'initialisation du compte administrateur initial (`admin` / `Cronstash2026!Secure`).
5. La compilation et le déploiement des fichiers statiques SPA SvelteKit.
6. L'activation du service Systemd `cronstash.service` et la configuration du reverse proxy Nginx sur le port `8080`.

Accédez à l'application via votre navigateur :
```text
http://<ip-serveur>:8080
```

---

## 💻 Moteur CLI & Crontab

Cronstash dispose d'une interface en ligne de commande directe appelée par le daemon `cron` système :

```bash
# Exécution d'une tâche de sauvegarde spécifique par ID
/opt/cronstash/venv/bin/python /opt/cronstash/cli.py run-job --id <job_id>

# Forcer l'exécution d'une tâche même si inactive
/opt/cronstash/venv/bin/python /opt/cronstash/cli.py run-job --id <job_id> --force

# Régénération manuelle du fichier /etc/cron.d/cronstash
/opt/cronstash/venv/bin/python /opt/cronstash/cli.py sync-cron

# Création ou réinitialisation d'un mot de passe admin
/opt/cronstash/venv/bin/python /opt/cronstash/cli.py init-admin --username admin --password "NouveauMotDePasse!"

# Affichage des tâches configurées
/opt/cronstash/venv/bin/python /opt/cronstash/cli.py list-jobs
```

Format du fichier `/etc/cron.d/cronstash` généré :
```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Job ID 1 : Backup PG Prod (production_db)
0 2 * * * root /opt/cronstash/venv/bin/python /opt/cronstash/cli.py run-job --id 1 >> /var/log/cronstash/cron.log 2>&1
```

---

## 🔄 Algorithme de Rétention GFS (Grandfather-Father-Son)

Après chaque sauvegarde réussie, le moteur applique automatiquement la purge GFS :
1. **Fils (Son / Daily)** : Conserve les $N_1$ sauvegardes les plus récentes (à raison d'une archive par jour).
2. **Père (Father / Weekly)** : Conserve les $N_2$ sauvegardes hebdomadaires (privilégiant celles prises le dimanche).
3. **Grand-père (Grandfather / Monthly)** : Conserve les $N_3$ sauvegardes mensuelles (privilégiant celles prises le 1er du mois).
4. **Purge** : Tous les fichiers hors de l'union de ces trois ensembles sont supprimés physiquement du disque et les métadonnées de libération d'espace sont journalisées.

---

## 🔔 Système de Notifications

- **SMTP** : Emails HTML soignés intégrant le badge d'état, tableau récapitulatif (serveur, base, taille, durée, horodatage) et rapport d'erreur formaté.
- **Discord** : Webhook avec Embed riche (couleurs `0x10B981` vert ou `0xEF4444` rouge, champs détaillés).
- Boutons de test instantané disponibles dans l'onglet **Notifications** de l'IHM.

---

## 🔒 Sécurité

- Mots de passe chiffrés avec **Argon2id** (`argon2-cffi` avec `time_cost=3`, `memory_cost=64MiB`, `parallelism=4`).
- Jetons JWT sécurisés transmis via cookies **HTTPOnly**, **SameSite=Strict**.
- Protection contre les attaques par traversée de chemin (*Path Traversal*) dans le téléchargement et la suppression d'archives.
