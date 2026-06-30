# 📄 → 🌐 Convertisseur PDF → HTML

Une application web simple (et un outil en ligne de commande) pour convertir
des fichiers PDF en HTML, avec conservation de la mise en page et des images.

La conversion s'appuie sur [PyMuPDF](https://pymupdf.readthedocs.io/) et tout
se passe **localement** : aucun fichier n'est conservé sur le serveur.

## ✨ Fonctionnalités

- **Glisser-déposer** d'un PDF dans le navigateur
- **3 modes de conversion** :
  - `layout` — fidèle à la mise en page (positions absolues, images intégrées)
  - `reflow` — texte réagençable et responsive (plus accessible)
  - `text` — texte brut échappé
- **Prévisualisation** instantanée dans un cadre isolé (iframe sandbox)
- **Téléchargement** du fichier HTML autonome (images embarquées en base64)
- **Outil CLI** réutilisable
- Validation des entrées (type, signature, taille, PDF protégés)
- Suite de **tests** automatisés

## 🚀 Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## 🖥️ Lancer l'application web

```bash
python app.py
```

Puis ouvrez <http://127.0.0.1:5000>.

Variables d'environnement optionnelles :

| Variable        | Défaut | Description                              |
|-----------------|--------|------------------------------------------|
| `PORT`          | `5000` | Port d'écoute                            |
| `MAX_UPLOAD_MB` | `16`   | Taille maximale d'un upload (Mo)         |
| `MAX_PAGES`     | `200`  | Nombre maximal de pages converties       |
| `DEBUG`         | —      | Active le mode debug Flask si défini     |

## 🛠️ Utilisation en ligne de commande

```bash
# Conversion fidèle à la mise en page (défaut)
python converter.py document.pdf

# Choisir le mode et le fichier de sortie
python converter.py document.pdf -m reflow -o sortie.html

# Limiter le nombre de pages
python converter.py gros-document.pdf --max-pages 10
```

## 🔌 API HTTP

| Méthode | Route           | Description                                  |
|---------|-----------------|----------------------------------------------|
| `GET`   | `/`             | Interface web                                |
| `POST`  | `/api/convert`  | Convertit et renvoie le HTML en JSON         |
| `POST`  | `/api/download` | Convertit et renvoie le fichier HTML         |
| `GET`   | `/health`       | Vérification de l'état du service            |

Les routes de conversion attendent un `multipart/form-data` avec les champs
`file` (le PDF) et `mode` (`layout` | `reflow` | `text`).

Exemple avec `curl` :

```bash
curl -F "file=@document.pdf" -F "mode=reflow" \
     http://127.0.0.1:5000/api/download -o sortie.html
```

## 🧪 Tests

```bash
pip install pytest
pytest
```

## 📁 Structure du projet

```
.
├── app.py              # Application web Flask
├── converter.py        # Cœur de conversion + CLI
├── requirements.txt
├── templates/
│   └── index.html      # Interface
├── static/
│   ├── style.css
│   └── script.js
└── tests/
    └── test_converter.py
```

## 📝 Licence

MIT
