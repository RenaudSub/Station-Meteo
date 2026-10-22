# Procédure d’installation de Station-Météo

**Version documentée : v1.3.0**  
**Dépôt :** [RenaudSub/Station-Meteo](https://github.com/RenaudSub/Station-Meteo)  
**Téléchargements :** [versions publiées](https://github.com/RenaudSub/Station-Meteo/releases/latest)

Station-Météo est une intégration personnalisée pour Home Assistant. Elle s’installe soit avec HACS en ajoutant le dépôt comme dépôt personnalisé, soit en copiant son dossier dans la configuration de Home Assistant.

## Avant de commencer

- Vérifiez que Home Assistant fonctionne et qu’une sauvegarde récente est disponible.
- Pour la méthode HACS, HACS doit déjà être installé et visible dans la barre latérale.
- Pour la méthode manuelle, il faut pouvoir accéder au dossier de configuration de Home Assistant, généralement `/config`.
- Utilisez de préférence la dernière version publiée dans la page [Releases](https://github.com/RenaudSub/Station-Meteo/releases), actuellement v1.3.0.

## Méthode 1 — Installation avec HACS et dépôt personnalisé

### Ajouter le dépôt à HACS

1. Ouvrez **HACS** dans la barre latérale de Home Assistant.
2. Ouvrez la page **Intégrations** de HACS.
3. Dans le menu **⋮** en haut à droite, choisissez **Dépôts personnalisés**.
4. Collez l’adresse suivante dans le champ du dépôt :

   `https://github.com/RenaudSub/Station-Meteo`

5. Choisissez le type **Intégration**.
6. Cliquez sur **Ajouter**.
7. Revenez à la page des intégrations HACS, recherchez **Station-Météo**, ouvrez sa fiche et choisissez **Télécharger**.
8. Si Home Assistant ou HACS demande un redémarrage, redémarrez Home Assistant. Si aucun message ne s’affiche, effectuez tout de même un redémarrage de Home Assistant pour charger proprement l’intégration.

### Ajouter l’intégration dans Home Assistant

1. Ouvrez **Paramètres → Appareils et services**.
2. Cliquez sur **Ajouter une intégration**.
3. Recherchez **Station Météo** puis sélectionnez-la.
4. Une fois l’intégration chargée, ouvrez son panneau depuis la barre latérale.

## Méthode 2 — Installation manuelle

### Copier les fichiers

1. Ouvrez la page [Releases de Station-Météo](https://github.com/RenaudSub/Station-Meteo/releases/latest) et téléchargez l’archive de la dernière version publiée.
2. Décompressez l’archive sur votre ordinateur.
3. Dans l’archive, repérez le dossier `custom_components/station_meteo`.
4. Copiez le dossier `station_meteo` dans le dossier `custom_components` de Home Assistant. Créez `custom_components` s’il n’existe pas.

Le chemin final doit être exactement :

```text
/config/custom_components/station_meteo/manifest.json
```

Vérifiez qu’il n’y a pas un dossier supplémentaire entre `custom_components` et `station_meteo`. Par exemple, ce chemin serait incorrect :

```text
/config/custom_components/Station-Meteo/custom_components/station_meteo/manifest.json
```

Vous pouvez copier les fichiers avec l’éditeur de fichiers, Samba, SSH ou un autre moyen d’accès à `/config`.

### Redémarrer et ajouter l’intégration

1. Dans Home Assistant, ouvrez **Paramètres → Système → Redémarrer** et redémarrez Home Assistant.
2. Après le redémarrage, ouvrez **Paramètres → Appareils et services**.
3. Cliquez sur **Ajouter une intégration**.
4. Recherchez **Station Météo** puis sélectionnez-la.
5. Ouvrez le panneau **Station-Météo** depuis la barre latérale.

## Configuration initiale

1. Dans le panneau Station-Météo, cliquez sur la **roue dentée** pour ouvrir les réglages.
2. Lancez **Autoconfig**.
3. Sélectionnez l’entité météo à utiliser (`weather.…`).
4. Si vous le souhaitez, sélectionnez une source météo de repli lorsque le fournisseur principal ne fournit pas les prévisions nécessaires.
5. Enregistrez les réglages.

Le panneau peut ensuite être personnalisé depuis ses options. Les réglages disponibles dépendent des capteurs et des entités présents dans votre Home Assistant.

## Vérification et dépannage

- **Station Météo n’apparaît pas dans la recherche :** vérifiez le chemin `custom_components/station_meteo/manifest.json`, puis redémarrez Home Assistant. Dans le navigateur, faites aussi un rechargement forcé de la page (**Ctrl+F5**).
- **Le dépôt ne s’ajoute pas dans HACS :** confirmez que vous êtes dans **HACS → Intégrations**, que l’adresse du dépôt est complète et que le type choisi est **Intégration**.
- **Le panneau ne s’affiche pas ou reste ancien après une mise à jour :** redémarrez Home Assistant puis videz le cache de l’interface avec **Ctrl+F5**.
- **Une erreur apparaît au démarrage :** consultez **Paramètres → Système → Journaux** et recherchez les messages mentionnant `station_meteo`.

## Mise à jour

- **Avec HACS :** ouvrez HACS, recherchez Station-Météo et installez la mise à jour proposée. Redémarrez Home Assistant si HACS le demande ; après une mise à jour, un redémarrage est recommandé.
- **Manuellement :** téléchargez la nouvelle archive publiée, remplacez le dossier `/config/custom_components/station_meteo` par celui de la nouvelle version, puis redémarrez Home Assistant.

Ne mélangez pas les fichiers de plusieurs versions. Gardez une copie de l’ancien dossier si vous souhaitez pouvoir revenir en arrière.

## Liens utiles

- [Dépôt GitHub](https://github.com/RenaudSub/Station-Meteo)
- [Versions et archives](https://github.com/RenaudSub/Station-Meteo/releases)
- [Page du projet](https://logisub.com/station-meteo.html)
