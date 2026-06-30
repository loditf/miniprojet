# 🔄 Convertisseur PDF &amp; Images

Une application web simple (et des outils en ligne de commande) pour convertir
entre **PDF**, **HTML** et **images** :

- **PDF → HTML** (conservation de la mise en page et des images)
- **PNG → PDF** (et JPEG, GIF, BMP, TIFF — une image par page)
- **PDF → PNG** (rendu de chaque page, résolution réglable)
- **Éditeur PDF** (réorganiser, pivoter, supprimer, fusionner, ajouter du
  texte/filigrane, remplir des champs de formulaire)

Tout s'appuie sur [PyMuPDF](https://pymupdf.readthedocs.io/) et se passe
**localement** : aucun fichier n'est conservé sur le serveur.

## ✨ Fonctionnalités

- Interface à **onglets** avec **glisser-déposer**
- **PDF → HTML**, 3 modes :
  - `layout` — fidèle à la mise en page (positions absolues, images intégrées)
  - `reflow` — texte réagençable et responsive (plus accessible)
  - `text` — texte brut échappé
- **PNG → PDF** : assemble plusieurs images en un seul PDF, dans l'ordre choisi
- **PDF → PNG** : 1 page → PNG, plusieurs pages → archive ZIP ; DPI réglable
- **Éditeur PDF** (sans état, aucun stockage serveur) :
  - vignettes des pages, **glisser-déposer** pour réordonner
  - **pivoter** (90/180/270°) et **supprimer/restaurer** des pages
  - **fusionner** des PDF supplémentaires à la fin
  - **ajouter du texte / un filigrane** (position, taille, couleur, opacité, angle)
  - **remplir les champs** de formulaire (AcroForm) détectés automatiquement
  - une seule requête applique toutes les opérations et renvoie le PDF édité
- **Prévisualisation** HTML instantanée dans un cadre isolé (iframe sandbox)
- **Téléchargement** des fichiers produits (HTML autonome, PDF, PNG, ZIP)
- **Outils CLI** réutilisables (`converter.py`, `image_converter.py`)
- Validation des entrées (type, signature, taille, PDF protégés)
- Suite de **tests** automatisés (20 tests)

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

### PDF → HTML (`converter.py`)

```bash
# Conversion fidèle à la mise en page (défaut)
python converter.py document.pdf

# Choisir le mode et le fichier de sortie
python converter.py document.pdf -m reflow -o sortie.html

# Limiter le nombre de pages
python converter.py gros-document.pdf --max-pages 10
```

### Images ↔ PDF (`image_converter.py`)

```bash
# PNG (et autres images) -> PDF, une image par page
python image_converter.py to-pdf page1.png page2.jpg -o album.pdf

# PDF -> PNG, une image par page dans un dossier
python image_converter.py to-png document.pdf -o images/ --dpi 200
```

## 🔌 API HTTP

| Méthode | Route                  | Description                                       |
|---------|------------------------|---------------------------------------------------|
| `GET`   | `/`                    | Interface web                                     |
| `POST`  | `/api/convert`         | PDF → HTML, renvoie le HTML en JSON               |
| `POST`  | `/api/download`        | PDF → HTML, renvoie le fichier HTML               |
| `POST`  | `/api/images-to-pdf`   | Images → PDF, renvoie le fichier PDF              |
| `POST`  | `/api/pdf-to-images`   | PDF → PNG (PNG seul ou ZIP si plusieurs pages)    |
| `POST`  | `/api/pdf/inspect`     | Vignettes des pages + champs de formulaire (JSON) |
| `POST`  | `/api/pdf/edit`        | Applique les éditions, renvoie le PDF modifié     |
| `POST`  | `/api/pdf/merge`       | Fusionne plusieurs PDF en un seul                 |
| `GET`   | `/health`              | Vérification de l'état du service                 |

Les routes attendent un `multipart/form-data` :

- `/api/convert` & `/api/download` : `file` (PDF), `mode` (`layout`|`reflow`|`text`)
- `/api/images-to-pdf` : `images` (un ou plusieurs fichiers image)
- `/api/pdf-to-images` : `file` (PDF), `dpi` (optionnel, 36–600)
- `/api/pdf/inspect` : `file` (PDF)
- `/api/pdf/edit` : `file` (PDF), `spec` (JSON, voir ci-dessous),
  `append` (PDF supplémentaires facultatifs à fusionner)
- `/api/pdf/merge` : `files` (au moins deux PDF)

Format de `spec` pour `/api/pdf/edit` (toutes les clés sont optionnelles) :

```json
{
  "pages":    [{"src": 2, "rotate": 90}, {"src": 0}],
  "overlays": [{"page": 0, "text": "CONFIDENTIEL",
                "x": 0.2, "y": 0.5, "size": 40,
                "color": "#d00000", "opacity": 0.3, "rotate": 45}],
  "fields":   {"nom": "Dupont", "date": "2026-06-30"}
}
```

- `pages` : liste ordonnée des pages conservées (index d'origine `src`,
  rotation cumulée). Les pages absentes sont supprimées ; réordonner la liste
  réordonne le document.
- `overlays` : textes/filigranes ajoutés (positions `x`/`y` en fraction
  0–1 de la page).
- `fields` : valeurs des champs de formulaire, par nom.

Exemples avec `curl` :

```bash
# PDF -> HTML
curl -F "file=@document.pdf" -F "mode=reflow" \
     http://127.0.0.1:5000/api/download -o sortie.html

# PNG -> PDF
curl -F "images=@p1.png" -F "images=@p2.png" \
     http://127.0.0.1:5000/api/images-to-pdf -o album.pdf

# PDF -> PNG (ZIP si plusieurs pages)
curl -F "file=@document.pdf" -F "dpi=200" \
     http://127.0.0.1:5000/api/pdf-to-images -o pages.zip
```

## 🧪 Tests

```bash
pip install pytest
pytest
```

## 📁 Structure du projet

```
.
├── app.py                  # Application web Flask (toutes les routes)
├── converter.py            # PDF -> HTML + CLI
├── image_converter.py      # Images <-> PDF + CLI
├── pdf_editor.py           # Éditeur PDF (pages, texte, formulaires, fusion)
├── requirements.txt
├── templates/
│   └── index.html          # Interface à onglets
├── static/
│   ├── style.css
│   └── script.js
└── tests/
    ├── test_converter.py
    ├── test_image_converter.py
    └── test_pdf_editor.py
```

## 📝 Licence

MIT
