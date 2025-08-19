# Module POS Livraison - Documentation API

## Vue d'ensemble
Le module POS Livraison fournit une gestion complète des livraisons avec:
- 📊 Dashboard en temps réel
- 🚛 Gestion des files d'attente
- 📦 Livraisons partielles 
- 🏭 Sorties de stock
- 🧮 Calculs automatiques de farine
- 📱 API REST pour applications mobiles

## Fonctionnalités principales

### 🎯 Gestion des commandes
- Création de commandes à livrer
- Gestion des priorités (Normal, Urgent, Très urgent)
- Suivi d'état : En file d'attente → En cours → Livrée partielle → Livrée complète
- Calculs automatiques (montants, sacs de farine, poids)

### 📊 Dashboard Kanban
- Vue d'ensemble des livraisons en cours
- Statistiques en temps réel
- Indicateurs visuels par état

### 🚛 File d'attente intelligente
- Tri automatique par priorité
- Estimation des temps d'attente
- Gestion FIFO avec exceptions urgentes

### 📦 Livraisons partielles
- Livraisons multiples par commande
- Suivi détaillé par livreur
- Calculs automatiques de farine

## API REST Endpoints

### 🔍 Consultation

#### Obtenir toutes les commandes actives
```
GET /api/livraison/commandes
Response: {
  "status": "success",
  "data": [
    {
      "id": 1,
      "name": "LIV-00001",
      "client_card": "CARD001",
      "client_nom": "Bakary Diallo",
      "montant_total": 444000,
      "montant_livre": 222000,
      "montant_restant": 222000,
      "etat": "en_cours",
      "priority": "1",
      "sacs_farine_total": 1.0,
      "poids_farine_kg": 50.0
    }
  ]
}
```

#### Détails d'une commande
```
GET /api/livraison/commande/<id>
Response: {
  "status": "success",
  "data": {
    "id": 1,
    "name": "LIV-00001",
    "livraisons": [
      {
        "id": 1,
        "montant_livre": 222000,
        "sacs_farine": 1.0,
        "livreur": "Ibrahim Sacko"
      }
    ]
  }
}
```

#### File d'attente
```
GET /api/livraison/queue
Response: {
  "status": "success", 
  "data": [
    {
      "position": 1,
      "id": 2,
      "name": "LIV-00002",
      "priority": "1",
      "temps_attente_estime": 0.5
    }
  ]
}
```

#### Statistiques
```
GET /api/livraison/stats
Response: {
  "status": "success",
  "data": {
    "commandes": {
      "en_queue": 5,
      "en_cours": 3,
      "livrees_partielles": 2,
      "total": 10
    },
    "livraisons_today": {
      "nombre": 8,
      "sacs_farine": 12.5,
      "montant": 2775000
    }
  }
}
```

### ✏️ Création

#### Nouvelle livraison partielle
```
POST /api/livraison/nouvelle_livraison
Body: {
  "commande_id": 1,
  "montant_livre": 222000,
  "livreur": "Moussa Diabaté",
  "notes": "Livraison du matin"
}
Response: {
  "status": "success",
  "message": "Livraison créée avec succès",
  "livraison_id": 5
}
```

#### Nouvelle sortie de stock
```
POST /api/livraison/sortie_stock
Body: {
  "motif": "Contrôle qualité",
  "quantite_sacs": 2,
  "type": "interne",
  "responsable": "Seydou Camara",
  "notes": "Tests hebdomadaires"
}
Response: {
  "status": "success",
  "message": "Sortie de stock créée avec succès",
  "sortie_id": 3
}
```

## Configuration

### Paramètres système
- `pos_livraison.prix_sac` : Prix d'un sac de farine (défaut: 222000)
- `pos_livraison.poids_sac` : Poids d'un sac en kg (défaut: 50)

### Numérotation automatique
- Commandes : LIV-00001, LIV-00002...
- Livraisons : LP-00001, LP-00002...
- Sorties : SOR-00001, SOR-00002...

## Calculs automatiques

### Sacs de farine
```
Nombre de sacs = Montant livré ÷ Prix par sac
```

### Poids en kg
```
Poids total = Nombre de sacs × Poids par sac
```

## Types de sorties de stock
- 🔧 **Usage interne** : Utilisation interne normale
- ❌ **Produit abîmé** : Marchandise endommagée
- 📉 **Perte** : Pertes diverses
- 🎁 **Don** : Dons et cadeaux
- 📋 **Autres** : Autres motifs

## Priorités des commandes
- 🟢 **Normal (0)** : Traitement standard
- 🟡 **Urgent (1)** : Traitement prioritaire 
- 🔴 **Très urgent (2)** : Traitement immédiat

## États des commandes
1. 📋 **En file d'attente** : Nouvelle commande
2. 🚛 **En cours de livraison** : Livraison démarrée
3. 📦 **Livrée partielle** : Livraison incomplète
4. ✅ **Livrée complète** : Livraison terminée
5. ❌ **Annulée** : Commande annulée

## Interface utilisateur

### Menu principal 🚚 POS Livraison
- 📊 **Dashboard** : Vue d'ensemble et statistiques
- 📦 **Commandes** : Gestion des commandes
  - Toutes les commandes
  - File d'attente
  - ➕ Nouvelle commande
- 🔧 **Opérations**
  - Livraisons effectuées
  - Sorties de stock  
  - ➕ Nouvelle sortie

### Vue Dashboard
- Cartes kanban par commande
- Codes couleur par état
- Statistiques temps réel
- Actions rapides

### Fonctionnalités avancées
- Boutons d'action contextuels
- Filtres et recherche
- Export des données
- Notifications automatiques

## Intégration mobile
L'API REST permet l'intégration avec des applications mobiles pour:
- Scan de codes barres clients
- Saisie rapide des livraisons
- Consultation de la file d'attente
- Gestion des sorties de stock sur le terrain

## Support
Module développé pour Odoo 15 avec support des fonctionnalités:
- Multi-langue (interface en français)
- Calculs automatiques
- Séquences personnalisées
- API REST complète
- Dashboard interactif
