# Screen and interaction matrix

Status: consolidated V1 visual reference. State IDs in this matrix belong to the replacement V1 UX design; they supersede both original boards. They are visual/behavioral references, not individual use cases or executed QA tests. Actual application strings and interaction instructions below are in Catalan. The authoritative use-case definitions and route/validation contracts live in `../specs/`.

## Menú setmanal

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| M01 | Setmana actual | Habitual | F01-UC02 | Consulta els 14 àpats i obre un plat. |
| M02 | Setmana en mòbil | Habitual | F01-UC02 | Canvia el dispositiu a mòbil; desplaça’t pels dies. |
| M03 | Navegació entre setmanes | Habitual | F01-UC03 | Fes servir les fletxes i torna a Avui. |
| M04 | Setmana futura sense menú | Buit | F01-UC01, F01-UC03 | Crea el menú; els 14 buits copien la plantilla. |
| M05 | Setmana passada amb menú | Només consulta | F01-UC02, F01-UC03 | Obre un plat i la compra; no hi ha accions d’edició. |
| M06 | Setmana passada sense menú | Buit | F01-UC03 | No hi ha botó per crear una setmana passada. |
| M07 | Nom llarg i setmana parcial | Límit | F01-UC02 | Consulta el nom complet obrint el plat. |
| M08 | Menú acabat de crear | Buit | F01-UC01 | Tria plats en els buits pendents. |
| M09 | Setmana del canvi d’any | Límit | F01-UC03 | Navega al gener amb les fletxes. |

## Tria de plats

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| P01 | Suggeriments de la plantilla | Habitual | F03-UC01, F02-UC01 | Tria un plat de la categoria suggerida. |
| P02 | Cerca pel nom | Habitual | F03-UC02 | Escriu o esborra el text de cerca. |
| P03 | Tots els plats | Habitual | F03-UC03, F02-UC01 | Tria qualsevol plat, encara que no coincideixi amb la preferència. |
| P04 | Categoria sense plats | Buit | F03-UC01, F03-UC03 | Mostra tots els plats o canvia la categoria. |
| P05 | Cerca sense resultats | Buit | F03-UC02 | Neteja la cerca sense sortir del selector. |
| P06 | Ordre de suggeriments | Límit | F03-UC01, F03-UC03 | Compara els plats ordinaris i d’ocasió especial; els arxivats no hi apareixen. |
| P07 | Buit sense suggeriment | Límit | F02-UC01, F03-UC03 | La tria comença amb totes les categories. |
| P08 | Plat desat | Èxit | F02-UC01 | Reobre el plat del menú. |
| P09 | Canvia un plat | Habitual | F02-UC02 | Tria un altre plat o cancel·la; l’original es conserva fins a desar. |

## Planificació i canvis

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| S01 | Fitxa i accions del menú | Habitual | F02-UC02, F02-UC03, F02-UC04, F02-UC05, F02-UC06, F06-UC01 | Obre les accions del plat i l’editor de recepta en una setmana editable. |
| S02 | Retira un plat | Decisió | F02-UC03 | Confirma o cancel·la; el buit torna a pendent. |
| S03 | Omet un àpat pendent | Decisió | F02-UC04 | Prem Omet aquest àpat. |
| S04 | Omet un àpat seleccionat | Decisió | F02-UC04 | Confirma la retirada i omissió. |
| S05 | Àpat omès | Habitual | F02-UC04 | Torna a planificar; no es recupera l’antic plat. |
| S06 | Tria la destinació | Habitual | F02-UC05, F02-UC06 | Tria un buit pendent o un altre plat. |
| S07 | Intercanvi completat | Èxit | F02-UC06, F02-UC07 | Els plats canvien de posició; Desfés restaura els dos. |
| S08 | Moviment completat | Èxit | F02-UC05, F02-UC07 | L’origen és pendent. Desfés restaura les posicions. |
| S09 | Destinació omesa | Decisió | F02-UC05 | Confirma la substitució de l’omissió o cancel·la. |
| S10 | Desfer el canvi | Èxit | F02-UC07 | Comprova la restauració; no hi ha un segon Desfés. |
| S11 | Desfer ja no disponible | Límit | F02-UC07 | Una edició posterior invalida Desfés. |
| S12 | Error durant el moviment | Error | F02-UC05, F02-UC06 | No s’ha desat cap canvi; torna a triar la destinació. |

## Plantilla

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| T01 | Plantilla setmanal | Habitual | F04-UC01 | Consulta les 14 categories sense plats assignats. |
| T02 | Canvia la categoria | Habitual | F04-UC02 | Tria una categoria i desa només la posició. |
| T03 | Deixa un àpat lliure | Decisió | F04-UC03 | Tria Lliure i desa. |
| T04 | Plantilla actualitzada | Èxit | F04-UC02, F04-UC03 | Torna al menú; els suggeriments copiats no han canviat. |

## Catàleg de plats

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| D01 | Catàleg actiu | Habitual | F05-UC01 | Filtra o obre una fitxa de plat. |
| D02 | Cerca al catàleg | Habitual | F05-UC02 | Escriu text per cercar. |
| D03 | Catàleg sense resultats | Buit | F05-UC02 | Neteja la cerca. |
| D04 | Nou plat | Habitual | F05-UC03 | Introdueix nom, categories i preferència; desa. |
| D05 | Dades del plat no vàlides | Error | F05-UC03, F05-UC04 | Corregeix el camp destacat; conserva la resta. |
| D06 | Edita un plat | Habitual | F05-UC04 | Canvia les dades i comprova el menú actual. |
| D07 | Arxiva un plat | Decisió | F05-UC05 | Confirma; les assignacions existents es conserven. |
| D08 | Plats arxivats | Habitual | F05-UC01, F05-UC06 | Obre un arxivat i restaura’l. |
| D09 | Restaura un plat | Decisió | F05-UC06 | Confirma; torna a ser seleccionable. |
| D10 | Cap plat arxivat | Buit | F05-UC01 | Torna a Plats actius. |

## Receptes

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| R01 | Recepta publicada | Habitual | F06-UC01 | Consulta ingredients per a 2 adults i preparació. |
| R02 | Recepta pendent | Buit | F06-UC01, F06-UC02 | No hi ha quantitats inventades; obre l’editor. |
| R03 | Edita la recepta | Habitual | F06-UC02 | Afegeix o retira ingredients i edita la preparació. |
| R04 | Ingredient al gust | Límit | F06-UC02 | Marca Al gust; quantitat i unitat no són aplicables. |
| R05 | Quantitat incorrecta | Error | F06-UC02, F06-UC03 | Corregeix la quantitat negativa; conserva el formulari. |
| R06 | Esborrany desat | Èxit | F06-UC03 | Consulta el contingut provisional i comprova la quantitat pendent. |
| R07 | Publicació incompleta | Error | F06-UC04 | Completa preparació i ingredients abans de publicar. |
| R08 | Recepta publicada correctament | Èxit | F06-UC04 | Consulta la versió efectiva. |
| R09 | Canvis encara no publicats | Límit | F06-UC01, F06-UC03, F06-UC04 | La fitxa efectiva no canvia fins a publicar. |
| R10 | Recepta històrica | Només consulta | F06-UC01 | Consulta el contingut desat de la setmana passada. |

## Llista de la compra

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| C01 | Compra setmanal parcial | Habitual | F07-UC01 | Consulta avisos, ingredients, ajustos i productes manuals. |
| C02 | Llista d’una setmana buida | Buit | F07-UC01, F07-UC02 | Afegeix un producte manual encara que no hi hagi plats. |
| C03 | Afegeix un producte | Habitual | F07-UC02 | Desa un extra amb quantitat i unitat o sense totes dues. |
| C04 | Edita un producte manual | Habitual | F07-UC02 | Modifica la quantitat; el marcatge es conserva. |
| C05 | Elimina un producte manual | Decisió | F07-UC02 | Confirma l’eliminació de l’extra, no dels ingredients. |
| C06 | Ajusta quantitat calculada | Habitual | F07-UC03 | Introdueix una quantitat positiva i conserva la base visible. |
| C07 | Ajust i restabliment | Èxit | F07-UC03 | Obre Ajusta i prem Restableix per tornar a la quantitat calculada. |
| C08 | Ajust sense ingredient calculat | Límit | F07-UC03 | Revisa o descarta explícitament l’ajust. |
| C09 | Unitats incompatibles i al gust | Límit | F07-UC01, F07-UC03 | Pes i unitats apareixen en files diferents; Al gust no és ajustable. |
| C10 | Productes comprats | Èxit | F07-UC04 | Marca i desmarca; navega i torna a la compra. |
| C11 | Tots els àpats omesos | Buit | F07-UC01 | No hi ha avís de buits pendents ni ingredients calculats. |
| C12 | Compra històrica | Només consulta | F07-UC01 | No es poden editar quantitats ni marcar productes. |
| C13 | Setmana sense menú a la compra | Buit | F07-UC01 | Ves al menú per crear la setmana abans d’afegir extres. |

## Errors i recuperació

| State | Screen / state (Catalan) | Type | Use cases | Expected interaction (Catalan) |
|---|---|---|---|---|
| X01 | Formulari amb canvis sense desar | Decisió | F06-UC02 | Continua editant o descarta els canvis. |
| X02 | Edició concurrent | Error | F06-UC03, F05-UC04 | Compara la versió desada amb els teus canvis abans de tornar a enviar el formulari. |
| X03 | Servidor no disponible | Error | F01-UC02 | Reintenta quan el servidor estigui disponible. |
| X04 | Carregant dades | Espera | F01-UC02 | Exemple de progrés opcional mentre hi ha una petició en curs. |
| X05 | Error en desar el formulari | Error | F06-UC03 | Simula un primer desament fallit i reintenta amb els mateixos camps. |
| X06 | Element no trobat | Error | F05-UC01 | Torna al catàleg. |
| X07 | Acció no permesa en setmana passada | Error | F01-UC03 | Mostra la prohibició; conserva la setmana en consulta. |

## Cross-feature coverage

For every use-case ID the following entries provide the visual references (some entries cover multiple use cases):

| Use case | UX states |
|---|---|
| F01-UC01 | M04, M08 |
| F01-UC02 | M01, M02, M05, M07, X03, X04 |
| F01-UC03 | M03, M04, M05, M06, M09, X07 |
| F02-UC01 | P01, P03, P07, P08 |
| F02-UC02 | P09, S01 |
| F02-UC03 | S01, S02 |
| F02-UC04 | S01, S03, S04, S05 |
| F02-UC05 | S01, S06, S08, S09, S12 |
| F02-UC06 | S01, S06, S07, S12 |
| F02-UC07 | S07, S08, S10, S11 |
| F03-UC01 | P01, P04, P06 |
| F03-UC02 | P02, P05 |
| F03-UC03 | P03, P04, P06, P07 |
| F04-UC01 | T01 |
| F04-UC02 | T02, T04 |
| F04-UC03 | T03, T04 |
| F05-UC01 | D01, D08, D10, X06 |
| F05-UC02 | D02, D03 |
| F05-UC03 | D04, D05 |
| F05-UC04 | D05, D06, X02 |
| F05-UC05 | D07 |
| F05-UC06 | D08, D09 |
| F06-UC01 | S01, R01, R02, R09, R10 |
| F06-UC02 | R02, R03, R04, R05, X01 |
| F06-UC03 | R05, R06, R09, X02, X05 |
| F06-UC04 | R07, R08, R09 |
| F07-UC01 | C01, C02, C09, C11, C12, C13 |
| F07-UC02 | C02, C03, C04, C05 |
| F07-UC03 | C06, C07, C08, C09 |
| F07-UC04 | C10 |
