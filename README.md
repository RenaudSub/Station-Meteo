# Station Météo — v0.10.0

Cette intégration personnalisée Home Assistant a été créée pour exploiter les données de la station météo **Ecowitt WS90** et les présenter dans un panneau dédié, clair et personnalisable. Elle s’appuie sur les capteurs disponibles dans Home Assistant, notamment via BTHome, et propose une interface adaptée aux ordinateurs, tablettes et smartphones, en français, anglais et espagnol.

### Vue d’ensemble

[![Vue d’ensemble](https://logisub.com/assets/sm-vue1.jpg?v=0.10.0)](https://logisub.com/assets/sm-vue1.jpg?v=0.10.0)

### Configuration générale

[![Configuration générale](https://logisub.com/assets/sm-config.jpg?v=0.10.0)](https://logisub.com/assets/sm-config.jpg?v=0.10.0)

### Personnalisations

[![Personnalisations](https://logisub.com/assets/sm-perso.jpg?v=0.10.0)](https://logisub.com/assets/sm-perso.jpg?v=0.10.0)

### Gestion des notifications

[![Gestion des notifications](https://logisub.com/assets/sm-notif.jpg?v=0.10.0)](https://logisub.com/assets/sm-notif.jpg?v=0.10.0)

### Carte des Températures

[![Températures](https://logisub.com/assets/sm-temp.jpg?v=0.10.0)](https://logisub.com/assets/sm-temp.jpg?v=0.10.0)

### Carte Satéllite

[![Carte Satéllite](https://logisub.com/assets/sm-sat.jpg?v=0.10.0)](https://logisub.com/assets/sm-sat.jpg?v=0.10.0)

## Nouveautés v0.10.0

- Trois boutons supplémentaires : **Humidité**, **Pluies 24H** et **Vent en rafales**, sur la région Météociel `r8` par défaut.
- Les six boutons sont personnalisables : nom, cible, mode d'ouverture et case Afficher ; réinitialisation indépendante.
- Le satellite utilise par défaut l'animation Météociel **composition visible MTG/Meteosat12 sur la France**. L'animation GIF originale se lit automatiquement ; son horaire change sur chaque image.
- Les trois nouvelles cartes et le satellite s'affichent seuls, avec un bouton Actualiser et le lien Météociel en bas à droite. Les horodatages et crédits inscrits sur les images sont conservés, sans superposer une heure de téléchargement à l'heure réelle des observations.
- Les réglages existants sont conservés. Les nouveaux boutons s'ajoutent automatiquement. Le satellite EUMETSAT non personnalisé bascule vers le nouveau défaut Météociel ; un cadrage EUMETSAT personnalisé ou une cible différente reste conservé.

### Cartes météo personnalisables

**Personnalisation → Boutons des cartes météo** permet de changer le nom, la cible HTTPS et le mode d'ouverture de chaque bouton, de masquer un bouton ou de rétablir ses réglages par défaut. Les six boutons sont affichés par défaut. Enregistrer applique les modifications ; Annuler conserve les réglages enregistrés.

Le mode **Carte seule Météociel** accepte le radar de précipitations standard, la foudre directe, les pages `humi.php`, `rr.php`, `vent-rafales.php` (mode 0), et les produits courants de `satellite.php`. La région des trois cartes de mesures peut être modifiée dans le lien, par exemple `region=r9`. Le cadrage et le zoom du radar et de la foudre viennent de `x`, `y` et `zoom`. Les archives et les autres produits du radar ne sont pas pris en charge. Pour une autre cible, choisir **Fenêtre intégrée** ou **Nouvel onglet**.

Le radar charge les douze images déclarées les plus récentes, avec lecture/pause et curseur temporel. Sa légende indique les intensités en mm/h. La foudre est un relevé fixe des trente dernières minutes, du jaune au rouge selon l'ancienneté des impacts. Une zone sans impacts n'est pas une erreur. Les observations sont créditées Météociel / Météo-France (radar) et Météociel / Blitzortung (foudre). Les images incomplètes sont exclues et les indisponibilités sont signalées.

Les cartes d'humidité, de pluie et de rafales sont les PNG originaux du fournisseur. Le satellite par défaut est son GIF animé. Date, horaire, légende et crédits restent dans l'image, avec le fuseau indiqué par Météociel ; le panneau ne les réinterprète pas. Le bouton Actualiser recharge les fichiers à nom fixe pour éviter une ancienne copie du navigateur.

Le mode **Animation EUMETSAT** reste sélectionnable dans Personnalisation. Il propose douze images GeoColour, lecture/pause, curseur et horodatage dans le fuseau Home Assistant. Le centre et le zoom sont configurables ; des coordonnées vides reprennent la station. Crédit EUMETSAT / NASA. Les images anciennes de plus de trois heures sont signalées.

Les images sont chargées à l'ouverture ou à l'actualisation, avec des métadonnées mutualisées pendant une minute (trente secondes pour la foudre). Home Assistant doit pouvoir accéder aux métadonnées et le navigateur aux images. Les sources Météociel sont celles utilisées par leur propre site et peuvent changer ; le lien source permet de consulter la carte originale.

## Nouveautés v0.9.0

- Cartes Météociel seules : radar animé et foudre des trente dernières minutes.
- Horodatage sur le radar et le satellite EUMETSAT, actualisation et lien source.
- Mesures locales à gauche et boutons à droite.
- Trois lignes lunaires compactes.

## Nouveautés v0.8.0

- Date du bandeau agrandie : « Dimanche 11 Octobre 2026 13h37min ».
- Conditions dans le titre : « Bulletin actuel : Éclaircies » ; les mesures restent dessous.
- Prochaines pleine lune et nouvelle lune calculées localement, avec l'heure locale et le changement d'heure.
- Lien des éphémérides aligné à droite et boutons de cartes personnalisables.

## Nouveautés v0.7.0

- Graphiques agrandis : axe vertical gradué, valeur brute et date/heure au survol ou au toucher, parcours par les flèches du clavier.
- Mini/maxi de la période affichée (12 heures), à droite du titre agrandi et dans les six cadres de capteurs. Les calculs utilisent les mesures brutes et excluent les états indisponibles.
- Infobulles sur les icônes météo du bandeau et des prévisions.
- Sous le bulletin : lever, coucher et midi solaire (zénith), phase de lune et estimation de la fraction éclairée.
- Éphémérides : saint, citation et dicton du jour depuis [ephemeride-jour.fr](https://www.ephemeride-jour.fr/), lien de source, une récupération réussie par jour. Les textes du fournisseur restent en français.

Dans **Configuration de la station**, les champs **Latitude** et **Longitude** peuvent rester vides pour utiliser l’emplacement de Home Assistant. Pour la station de cet exemple : `42.627506`, `2.593331`, altitude `247 m`. Les heures utilisent le fuseau de Home Assistant. Le « zénith » désigne ici le midi solaire (hauteur maximale du Soleil), pas un passage vertical au-dessus de l’observateur. Le calcul ne tient pas compte des reliefs qui masquent l’horizon.

La case des éphémérides permet de désactiver la récupération distante. Le panneau n’affiche jamais le texte de la veille comme celui du jour ; en cas d’échec, il affiche une indisponibilité et retente après une heure. Cette fonction dépend de la disponibilité et de la structure HTML du site, sans API publique utilisée. Le soleil et la lune sont calculés localement et restent disponibles sans ce site.

## Nouveautés v0.6.0

Les sept graphiques locaux (Vent, Température, Précipitations, Humidité de l’air, Indice UV, Rayonnement solaire, Pression) s’ouvrent dans une fenêtre presque pleine largeur en cliquant sur le tracé. Les couleurs, le fond, le remplissage et le lissage sont identiques au graphique original. Le titre, la valeur courante, l’unité et les heures de début/fin sont affichés. Fermez avec la croix en haut à droite ou Échap. Le petit graphique reste visible dessous. La consultation fonctionne aussi sans droits administrateur et sur téléphone. Si aucune donnée n’est enregistrée, la fenêtre indique l’absence d’historique. Les valeurs de cette fenêtre sont un aperçu au moment de l’ouverture ; fermez et rouvrez pour actualiser.

« Intensité de pluie » est renommé **Précipitations**. Ce changement de libellé ne modifie pas les capteurs : le taux reste en mm/h et le cumul est indiqué séparément en mm.

### Deux sources de prévisions

Dans **Configuration de la station**, sélectionnez :

1. **Source météo principale** : votre entité Météo-France.
2. **Source météo de repli** : votre entité Met.no, déjà ajoutée dans Home Assistant.
3. Cliquez sur **Enregistrer**.

La source de repli est facultative et n’est pas choisie automatiquement. Un autre fournisseur compatible avec les prévisions Home Assistant peut être utilisé. Les anciennes associations sont conservées, le nouveau champ reste vide jusqu’à votre sélection.

La source principale est prioritaire champ par champ. Une donnée absente (`null`), non numérique ou invalide est complétée par le repli uniquement pour la même heure UTC ; les prévisions quotidiennes sont alignées par date locale Home Assistant. Les valeurs **0** sont conservées et les valeurs négatives de température restent valides. Les créneaux horaires déjà passés et les journées passées sont écartés. Aucun décalage vers une heure voisine ni interpolation n’est effectué. Si le principal ne fournit pas un créneau, celui du repli est affiché. Les données absentes des deux sources restent `—`.

Températures, vent et pluie sont convertis dans des unités communes avant la fusion. Le graphique affiche des probabilités (%) si elles sont fournies ; sinon il utilise les quantités (mm), avec un repère bleu aux valeurs zéro. Les noms des sources utilisées et la provenance des probabilités de pluie figurent sous les prévisions. Un mélange de fournisseurs complète les informations mais ne constitue pas une nouvelle prévision calculée.

Les prévisions sont relues toutes les dix minutes et à l’enregistrement. Le retour du principal est appliqué à la prochaine lecture. Les alertes d’orage utilisent la même fusion côté serveur, indépendamment du panneau ouvert ou fermé. Les observations du WS90 restent les mesures locales ; la source secondaire ne les remplace jamais.

L’altitude par défaut pour une nouvelle configuration est **247 m**. Les configurations existantes gardent leur valeur : corrigez manuellement une ancienne altitude de 580 m si nécessaire.

## Photo personnelle : bouton Parcourir (v0.6.0)

1. Ouvrez la roue dentée, puis cliquez sur **Parcourir** sous « Photo du bandeau ».
2. Choisissez une photo **JPG, PNG ou WebP**, maximum **8 Mo** et **40 mégapixels**.
3. Attendez l’aperçu, puis cliquez sur **Enregistrer**.

Le navigateur transfère la photo à Home Assistant avec votre session actuelle.
Aucune manipulation SSH, aucun chemin à saisir. Les transferts sont réservés aux
administrateurs. L’intégration vérifie le contenu réel de l’image et lui attribue
un nom unique ; le nom du fichier choisi ne sert jamais à construire un chemin.

Les photos sont conservées dans `/config/station_meteo/images`, servies sous
`/station_meteo/images/`. Ce répertoire est séparé de `custom_components` afin que
la photo survive au remplacement du dossier de l’intégration. Les photos déjà
placées dans `frontend` peuvent aussi être sélectionnées directement avec
`/station_meteo/frontend/maison.jpg`.

**Annuler** conserve le bandeau actuellement enregistré. Le fichier transféré
reste stocké mais n’est pas appliqué. Les anciens transferts ne sont pas supprimés
automatiquement.

## Visuels et graphiques v0.5.0

- Les 15 icônes météo par défaut utilisent les WebP animés transparents fournis, sans les visuels Microsoft. Les fichiers sont conservés sans conversion. Les éléments image sont réutilisés lors des actualisations des valeurs pour conserver la lecture des animations.
- Icône du bandeau deux fois plus grande sur PC et tablette, taille adaptée et visible sur smartphone.
- Courbes Vent, Pression et Humidité adoucies : moyenne légère des voisins proches et tracé courbe sans dépassement des valeurs. Les mesures, minimums, maximums, rafales et alertes utilisent toujours les données brutes.
- Histogrammes de pluie horaire : repère bleu à zéro. Si la source fournit une probabilité, affichage en %. Sinon, quantités réelles prévues en mm. Météo-France dans HA 2026.9.4 fournit des quantités et aucune probabilité horaire. Une valeur absente reste inconnue ; elle n'est pas remplacée par zéro.
- Flèche de vent traversant le cadran de bord à bord dans le sens du déplacement de l'air. Vent du Sud (180°) : empennage au Sud et pointe au Nord. Le texte et l'angle indiquent toujours la provenance du vent.
- Personnalisation indépendante du cadran et de la flèche : boussole d'origine, boussole 3D fournie, flèche d'origine, flèche à plumes et flèche moderne, ou vos propres transferts. Les réglages de rotation personnelle restent appliqués.
- Le bandeau retrouve `landscape.svg` d'origine par défaut. La photo de Casefabre n'est plus incluse. Une photo personnelle déjà configurée est conservée ; videz le champ Photo du bandeau pour revenir au paysage.

Tous les visuels par défaut sont locaux. Le champ Photo du bandeau accepte aussi une URL HTTPS directe ou un chemin local autorisé. En cas d'image inaccessible, le paysage d'origine est affiché. Les icônes météo et les deux éléments de la boussole possèdent également un retour au visuel d'origine en cas d'échec de chargement.

## Modification v0.2.2

Les directions du vent sont écrites en toutes lettres dans le bloc Vent et le
bulletin : « Vent d’Ouest », « Vent du Sud », « Vent du Sud-Ouest », etc.
FR/EN/ES utilisent des phrases adaptées à chaque langue. Les abréviations sont
conservées uniquement sur la rose des vents.

## Correction v0.2.1

La lecture de l’historique définit maintenant explicitement `end_time` à l’heure
courante. Sans ce paramètre, une requête commençant il y a 30 h ne renvoyait que
24 h de données et excluait les 6 dernières heures : courbes et mini/maxi absents
pour une station récemment installée.

## Mise à jour depuis v0.1.0 / v0.2.0

Remplacez entièrement `/config/custom_components/station_meteo` par le dossier de
cette archive, puis redémarrez Home Assistant et faites **Ctrl + F5** dans le navigateur.
Ne supprimez pas l'intégration dans Appareils et services : les associations d'entités
et autres réglages existants sont conservés. Les notifications ajoutées restent désactivées.

## Installation manuelle

1. Décompressez `Station-Meteo-v0.10.0.zip` sur votre ordinateur.
2. Copiez le dossier **`custom_components/station_meteo`** dans
   **`/config/custom_components/station_meteo`** sur Home Assistant.
   Le fichier manifest doit être exactement à :
   `/config/custom_components/station_meteo/manifest.json`.
3. Redémarrez Home Assistant.
4. Ouvrez **Paramètres → Appareils et services → Ajouter une intégration**,
   recherchez **Station Météo**, puis validez.
5. Ouvrez **Station Météo** dans la barre latérale.
6. Cliquez sur la roue dentée, puis sur **Autoconfig**.
   L'appareil **SBWS-90CM D693** est présélectionné lorsqu'il est trouvé
   par son nom d'origine ou son adresse BTHome `C0:2C:ED:95:D6:93`.
7. Vérifiez les champs remplis et sélectionnez votre **source météo et prévisions**.
   Pour votre installation :
   `weather.meteo_france_forecast_for_city_casefabre_languedoc_roussillon_66_fr_casefabre`.
   Choisissez la source réelle proposée par Home Assistant si son identifiant a changé.
8. Cliquez sur **Enregistrer**.

Aucune ligne à ajouter dans `configuration.yaml`. Aucun module frontend à installer
séparément ni ressource Lovelace à ajouter. Home Assistant Core **2026.9.4 ou plus
récent** recommandé. Les tests d'API de cette version ont été exécutés avec 2026.9.4.
La compatibilité avec de futures versions reste à vérifier lors de leurs mises à jour.

## Configuration depuis la roue dentée

- Sélection d'entités individuelles par identifiant, avec recherche/suggestions.
- **Autoconfig** lit les registres Home Assistant et associe les capteurs du WS90.
  Il conserve les noms et identifiants d'origine. Les index BTHome `speed_1` et
  `speed_2` distinguent le vent des rafales : aucune déduction d'après leurs valeurs.
- Nom du lieu, altitude, langue automatique ou manuelle FR/EN/ES.
- Vent en km/h ou m/s ; conversion depuis les unités du capteur.
- Pression locale absolue, ou estimation au niveau de la mer utilisant l'altitude.
  La pression locale affichée par défaut n'est pas corrigée. Ne sélectionnez pas
  une correction si votre capteur fournit déjà une pression au niveau de la mer.
- Rayonnement solaire mesuré par un capteur W/m² ou estimation optionnelle à partir
  des lux. L'estimation est **désactivée par défaut**, marquée comme estimation et
  utilise un facteur configurable (126,7 lux par W/m² par défaut). Ce facteur dépend
  du spectre lumineux ; il ne remplace pas une mesure d'irradiance.
- Bulletin externe via un `sensor` ou `input_text`. Sans source de bulletin,
  un résumé des observations est produit. Il ajoute les fortes baisses/hausses de
  pression sur 3 heures et une mention de dégradation/amélioration **possible**.
  Le seuil par défaut est de 3 hPa sur 3 h, réglable dans l'onglet Notifications,
  même si l'envoi des notifications reste désactivé. Une baisse de pression seule
  n'annonce jamais un orage. Les mentions d'orage proviennent exclusivement de
  l'état courant ou des prévisions horaires de l'entité `weather` (horizon 3 h).
  Ces analyses sont également ajoutées après un bulletin externe sélectionné.
- Suggestions d'entités filtrées selon la mesure et exclusion des entités de
  l'intégration AdGuard, même renommées. Une saisie manuelle reste possible.

### Orientation personnelle de la rose des vents

Dans la roue dentée, indiquez la **direction devant vous / haut de l'écran** :
`155°` place le sud-est en haut. Le nord se retrouve à `205°` dans le dessin,
et un vent venant de `153°` est affiché à `−2°` par rapport au haut de l'écran.
Les lettres cardinales restent lisibles et la mesure réelle n'est pas modifiée.
Le trait orange en haut de la rose représente votre direction de regard.

Ce réglage est propre au navigateur et à la station, enregistré dans `localStorage`
après **Enregistrer**. Chaque ordinateur/tablette peut avoir une orientation différente.
**Annuler** n'applique rien. L'affichage reste nord en haut sur smartphone : l'orientation
personnelle s'applique si le petit côté de l'écran et la largeur de fenêtre sont ≥ 600 px
CSS. Une fenêtre étroite revient donc également au nord en haut. Effacer les données du
navigateur efface ce réglage. Les téléphones exceptionnellement grands/foldables sont
traités comme tablettes dès lors qu'ils dépassent ces dimensions.

### Notifications

Roue dentée → **Notifications**. Elles sont **désactivées par défaut** et aucun
destinataire n'est présélectionné. Choisissez une ou plusieurs actions `notify.*`
existantes (notamment `notify.mobile_app_*`) ou une notification persistante Home Assistant.
Les destinataires modernes exclusivement exposés comme entités `notify.*` sans action dédiée
ne sont pas pris en charge dans cette version.

Alertes disponibles : forte baisse de pression (défaut 3 hPa sur 3 h), pluie détectée,
rafales (défaut 60 km/h, alerte désactivée par défaut), orage indiqué actuellement
ou prévu dans les 3 prochaines heures par le fournisseur météo. Le service météo
est interrogé toutes les 10 minutes uniquement si l'alerte d'orage est activée et
que les prévisions horaires sont prises en charge.

La surveillance tourne **dans Home Assistant** toutes les minutes, panneau ouvert
ou fermé. Une condition persistante n'est pas renvoyée en boucle ; elle doit cesser
avant de se réarmer. Le délai minimum entre alertes du même type est configurable
(défaut 60 minutes). Si une condition est déjà présente lors de l'activation, elle
peut déclencher une alerte. Les valeurs indisponibles ne déclenchent pas d'alerte.
L'alerte de pression utilise des échantillons locaux en mémoire ; attendez 3 heures
après un redémarrage/rechargement ou changement de capteur. Les états d'alerte et délais
sont également réinitialisés au redémarrage. Un capteur absent interrompt son suivi.
Les messages suivent FR/EN/ES ; en mode automatique, les notifications utilisent la
langue générale de Home Assistant (le panneau suit la langue du navigateur HA).

Les autres réglages sont partagés par tous les utilisateurs et conservés après redémarrage
Home Assistant. Seuls les administrateurs peuvent les modifier. Les autres utilisateurs
peuvent consulter le panneau, dans la limite de leurs permissions Home Assistant.
Les champs restent en brouillon jusqu'à **Enregistrer** ; **Annuler** ne modifie rien.

## Mesures et limites connues

| Mesure | Source |
|---|---|
| Température / humidité de l'air | Capteurs BTHome WS90 |
| Vent / rafales / direction | Capteurs BTHome WS90 ; flèche dans le sens du déplacement de l’air, texte indiquant la provenance |
| UV / éclairement en lux | Capteurs BTHome WS90 |
| Pression / point de rosée | Capteurs BTHome WS90 |
| Pluie détectée / cumul mesuré en mm | Capteurs BTHome WS90 |
| Débit de pluie en mm/h | Capteur externe à sélectionner ; absence affichée par un tiret |
| Rayonnement en W/m² | Capteur externe ou estimation explicitement activée |
| Prévisions horaires / demain | Entité `weather` compatible avec `weather.get_forecasts` |
| RSSI | Entité signal BTHome si disponible/activée ; non créée par cette intégration |

L'entité de tension du supercondensateur n'est pas utilisée.
Les noms génériques « Humidité » et « Vitesse » de BTHome ne sont pas modifiés.
Les informations manquantes ou indisponibles s'affichent **—**, jamais comme zéro.
Autoconfig signale les entités désactivées ; activez celles souhaitées depuis BTHome,
puis relancez Autoconfig. Une entité dont le rôle est ambigu reste à choisir manuellement.

Les courbes locales, minima/maxima du jour et tendances utilisent **Historique/Recorder**.
Elles nécessitent des données enregistrées. Les minima/maxima portent sur les échantillons
disponibles pour la journée dans le fuseau Home Assistant. Le cumul quotidien est calculé
sur le compteur de pluie, avec prise en compte de ses remises à zéro, seulement lorsqu'un
échantillon de référence avant minuit et des données du jour sont disponibles. Sinon,
le panneau affiche **Cumul mesuré**, sans le présenter comme un cumul quotidien.
Les graphiques affichent jusqu'à 12 h d'historique local ; les données de 30 h sont
consultées pour les calculs journaliers. Les courbes sont relues toutes les 5 minutes,
les prévisions toutes les 10 minutes ; les valeurs instantanées suivent Home Assistant.
Sur téléphone, les cartes horaires défilent horizontalement.

Cette intégration exploite les données existantes : elle n'améliore pas la liaison
radio WS90 ↔ Shelly. Une coupure BTHome reste visible comme une indisponibilité.

## Dépannage

- **L'intégration n'apparaît pas** : vérifiez le chemin du manifest, redémarrez HA,
  puis actualisez votre navigateur. Consultez les journaux Home Assistant.
- **Panneau blanc après mise à jour** : faites `Ctrl + F5` ou videz le cache frontend
  de l'application mobile. Les fichiers statiques sont servis sans cache permanent.
- **Autoconfig ne trouve pas la station** : la station doit déjà être ajoutée à BTHome.
  Le menu permet de choisir un autre WS90 ou de renseigner chaque capteur manuellement.
- **Pas de prévisions** : choisissez l'entité `weather`, pas un capteur de couverture
  nuageuse. La source doit exposer les prévisions horaires et/ou journalières.
- **Pas de courbes** : vérifiez que Recorder enregistre les entités de la station.
- **Mesures indisponibles** : contrôlez BTHome et la fraîcheur des paquets sur le Shelly.
  Ne supprimez pas cette intégration pour résoudre une coupure radio.

## Validation de cette livraison

- Décodage de paquets WS90 d'exemple avec `bthome-ble` : vent/rafales, pluie et humidité,
  exclusion des entités désactivées et des rôles ambigus.
- Tests avec les API réelles Home Assistant **2026.9.4** : enregistrement/retrait du
  panneau, lecture du registre BTHome, routes statiques, stockage et droits administrateur.
  Le serveur HTTP est remplacé par un double de test pour l'enregistrement des routes.
- Tests navigateur Chromium avec état Home Assistant simulé : formats 1536×1024,
  820×1180 et 390×844 ; recherche/autoconfiguration, sauvegarde/annulation, FR/EN/ES,
  chaînes échappées, valeurs indisponibles et affichage pour un utilisateur non administrateur.
- Tests d'alertes avec vrais appels de service Home Assistant et destinataires simulés :
  activation, conversions Pa/hPa et m/s/km/h, déclenchement, réarmement, temporisation,
  fenêtre de pression complète et interruption, orage issu des prévisions.
- Tests navigateur complémentaires : AdGuard renommé exclu, sauvegarde des destinataires,
  orientation 155° persistante, annulation, rose nord en haut sur smartphone,
  bulletin avec pression et orage. Captures de notification et d'orientation tablette dans `docs`.
- Vérification syntaxique Python/JavaScript et concordance des fichiers de traduction.

**La livraison n'a pas été installée sur votre instance ni testée avec votre WS90 physique.**
Les premiers essais sur votre Home Assistant permettront de confirmer les données
réelles, les prévisions de Météo-France et le rendu des icônes natives Home Assistant.

## Développement

Sources dans `custom_components/station_meteo`. Les tests backend sont dans `tests`.
La validation des photos utilise Pillow 12.3.0, également fourni par HA Core 2026.9.4.

Installez les dépendances de `requirements-dev.txt` dans un environnement Python 3.14 :

```sh
PYTHONPATH=. pytest tests
```

Les fichiers dans `tests/browser` constituent une fixture autonome avec des données
fictives, réservée aux tests. Pour les tests du navigateur :

```sh
npm install --no-save playwright
npx playwright install chromium
python tests/browser/server.py
# Dans un autre terminal :
node tests/browser/check.cjs
```

Ce paquet contient également les aperçus PC et smartphone des tests simulés,
dans `docs`. Le paysage et les icônes météo sont inclus localement ; seule une image distante explicitement configurée est chargée depuis Internet.

## Icônes personnalisées (v0.6.0)

Roue dentée → **Personnalisation** : chaque ligne affiche l’icône par défaut à gauche, le nom de la condition puis **Parcourir** et le chemin de votre image. PNG, GIF et WebP transparents, fixes ou animés, ainsi que JPG sont acceptés (8 Mo maximum par fichier). Un aperçu apparaît après le transfert. Cliquez sur **Enregistrer** pour appliquer toutes les modifications au bandeau, aux prévisions horaires et à demain. **Défaut** rétablit l’icône originale de la ligne ; **Annuler** conserve la configuration précédente. Les 15 conditions Home Assistant peuvent être personnalisées indépendamment, avec une icône originale distincte pour chaque condition.

Les images sont conservées dans `/config/station_meteo/images`, y compris lors des mises à jour de l’intégration. Les chemins peuvent aussi être saisis manuellement (HTTPS ou chemin local autorisé). Une image personnalisée inaccessible est remplacée à l’affichage par l’icône originale. Si la préférence système « réduire les animations » est activée, les images météo locales sont figées par le navigateur dans un aperçu. Les images externes peuvent dépendre des permissions de leur serveur. Une extension GIF ou WebP ne garantit pas une animation : le fichier doit contenir plusieurs images.

### Personnaliser la boussole et la flèche

Roue dentée → **Personnalisation → Boussole et flèche**. Choisissez les modèles fournis dans les listes ou utilisez **Parcourir**. Cadran : PNG/WebP/GIF transparent avec le Nord en haut. Flèche : SVG transparent avec une pointe vers le haut, pivot au centre de son `viewBox`, empennage du côté opposé. Les deux calques sont alignés au centre et occupent le même carré. Les SVG sont affichés comme images, sans insertion de leur contenu dans le panneau. Le transfert accepte les formes, dégradés et filtres statiques ; scripts, événements, contenu HTML et ressources externes sont refusés. Limite : 8 Mo par fichier, 2 000 éléments pour les SVG.

Les réglages sont appliqués après **Enregistrer** et conservés après redémarrage. **Défaut** rétablit indépendamment le cadran ou la flèche. **Annuler** conserve les réglages précédents. Les images transférées restent dans `/config/station_meteo/images` lors des mises à jour.

Le modèle de boussole 3D fourni a le Nord en bas dans son image originale : son calque est automatiquement tourné de 180° avant d’appliquer votre orientation personnelle. Pour vos propres fichiers transférés, préparez le Nord en haut.
Les repères cardinaux du modèle 3D fourni restent droits et lisibles lorsque le cadran est tourné.
