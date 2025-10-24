# Correction erreur "Expected a string but was BOOLEAN at path $.result.data[0].client_nom"

## 🐛 Problème identifié

**Erreur:** `Expected a string but was BOOLEAN at path $.result.data[0].client_nom`

### Cause racine

L'API REST du module `pos_livraison` (fichier `controllers/main.py`) utilisait le champ **`client_nom`** qui **n'existe pas** dans le modèle `pos.caisse.commande`.

**Dans le modèle `pos_caisse/models/pos_caisse.py` (ligne 195):**
```python
client_name = fields.Char('Nom du client', help="Nom complet du client/vendeur")
```

Le champ correct s'appelle **`client_name`** (avec "name" en anglais), pas `client_nom`.

### Conséquence

Lorsqu'Odoo essaie d'accéder à un champ inexistant (`c.client_nom`), il retourne **`False`** (booléen) au lieu d'une chaîne de caractères, ce qui causait l'erreur JSON dans l'application mobile Android.

## ✅ Corrections appliquées

### Fichier: `pos_livraison/controllers/main.py`

**3 emplacements corrigés:**

#### 1. Endpoint `/api/livraison/commandes` (ligne ~182)

**Avant:**
```python
'client_nom': c.client_nom,
```

**Après:**
```python
'client_nom': c.client_name or '',
```

**Également corrigé la recherche (ligne ~174):**
```python
# Avant
domain += ['|', ('name', 'ilike', search), ('client_nom', 'ilike', search)]

# Après
domain += ['|', ('name', 'ilike', search), ('client_name', 'ilike', search)]
```

#### 2. Endpoint `/api/livraison/commande/detail` (ligne ~302)

**Avant:**
```python
'client_nom': c.client_nom,
```

**Après:**
```python
'client_nom': c.client_name or '',
```

#### 3. Endpoint `/api/livraison/queue` (ligne ~392)

**Avant:**
```python
'client_nom': c.client_nom,
```

**Après:**
```python
'client_nom': c.client_name or '',
```

## 📊 Impact

### Avant
- ❌ Erreur JSON: "Expected a string but was BOOLEAN"
- ❌ Application mobile crash lors de la récupération des commandes
- ❌ Recherche par nom de client ne fonctionnait pas

### Après
- ✅ `client_nom` renvoie correctement une chaîne de caractères
- ✅ Valeur par défaut `''` (chaîne vide) si `client_name` est NULL
- ✅ Recherche fonctionne sur le bon champ
- ✅ Application mobile peut parser correctement le JSON

## 🚀 Déploiement

### 1. Redémarrer le serveur Odoo

```powershell
# Arrêter le serveur
Ctrl+C

# Redémarrer
python C:\odoo\server\odoo-bin -c C:\odoo\server\odoo.conf
```

### 2. Tester l'API

```bash
# Tester avec curl ou Postman
POST /api/livraison/commandes
{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
        "etat": "en_queue"
    }
}

# Vérifier que client_nom est maintenant une string
```

### 3. Vérifier dans l'application mobile

- Ouvrir l'écran de livraison
- Vérifier que les commandes s'affichent correctement
- Vérifier que les noms de clients sont visibles

## 📝 Note importante

L'API REST continue d'exposer le champ sous le nom **`client_nom`** (avec "nom" en français) pour **compatibilité avec l'application mobile Android** qui attend ce nom de champ.

Seule la **source du mapping** a changé:
- **Avant:** `c.client_nom` (champ inexistant → False)
- **Après:** `c.client_name or ''` (champ correct → string)

Aucune modification n'est nécessaire dans l'application Android.

## ⚠️ Prévention

Pour éviter ce type d'erreur à l'avenir:

1. **Vérifier l'existence des champs** dans le modèle avant de les utiliser
2. **Utiliser `getattr()`** avec valeur par défaut pour les champs optionnels:
   ```python
   'field': getattr(c, 'field_name', '') or ''
   ```
3. **Tester l'API** après chaque modification avec des données réelles
4. **Activer le mode debug** Odoo pour voir les erreurs de champ manquant

## 🔍 Vérification

Pour vérifier que le champ existe dans le modèle:

```python
# Dans un shell Odoo
fields = request.env['pos.caisse.commande']._fields.keys()
print('client_nom' in fields)  # False
print('client_name' in fields)  # True
```
