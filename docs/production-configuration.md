# OptiMapper: configuración de producción

Proyecto: `optimapper-489016`. Backend: `optimapper-api`, región `europe-west1`.
Frontend: `https://optimapper.vercel.app/`.

El código se mantiene en `feat/time-aware-itineraries`. Cloud Run ejecuta una
imagen construida desde esa rama; no lee automáticamente los archivos locales ni
requiere fusionarlos con `main`. Vercel necesita su propio despliegue del frontend.

## Controles de consumo

Se habilitaron Places API (New), Routes API, Maps JavaScript API y Secret Manager.
En Service Usage se configuraron cuotas diarias por proyecto:

| Método / función | Máximo diario |
| --- | ---: |
| Places SearchNearby | 30 consultas |
| Places SearchText, incluida resolución de ciudad | 30 consultas |
| Places GetPlace | 30 consultas |
| Routes ComputeRouteMatrix | 300 elementos |
| Maps JavaScript: cargas de mapas 2D | 300 cargas |
| Fotos, reseñas adicionales, Autocomplete, mapas 3D y ComputeRoutes | 0 |

Para los campos que solicita esta aplicación, 31 días a esos límites equivalen
a como máximo 930 consultas por método de Places y 9.300 elementos/cargas de
Routes/Maps. Quedan por debajo de los cupos gratuitos de los SKU utilizados a
25 de octubre de 2026, suponiendo que no haya otro consumo de la misma cuenta.
Una cuota diaria se restablece cada día y puede impedir reabrir o recalcular un
viaje hasta el siguiente día si se consume por completo. Los viajes largos pueden
superar las 30 consultas de detalle permitidas al reabrirlos.

También se creó un presupuesto con corte para **Cloud Run**, limitado al proyecto:

- Importe: **1 EUR de consumo bruto estimado por mes**.
- Estado deseado: `CONFIGURED`; avisos al 50 %, 80 % y 100 %.
- El consumo bruto no descuenta el nivel gratuito ni otros créditos.
- Al alcanzar el importe, Google puede pausar las nuevas solicitudes de Cloud Run
  hasta el siguiente mes o hasta que se levante el límite.
- La aplicación del corte no es instantánea; puede haber sobrecostes por solicitudes
  en curso o retrasos de contabilización. No es una garantía de factura cero.
- El corte no incluye Artifact Registry, Cloud Build, Storage, Secret Manager,
  Google Maps, Anthropic ni Supabase.

Se conserva la alerta previa de 1 EUR para la cuenta de facturación. Esa alerta
por sí sola no corta el gasto.

Las sugerencias de Claude se pueden desactivar en producción con
`ENABLE_AI_SUGGESTIONS=false`. En ese modo se obtienen lugares de Google y se
estiman las duraciones por categoría sin consumir Anthropic. La clave existente
de Anthropic se conserva para poder reactivar la función posteriormente.

## Claves y secretos

- La clave privada de backend solo permite Places y Routes.
- Se guarda en Secret Manager como `optimapper-google-maps-key`, versión `1`.
- La cuenta de servicio de Cloud Run tiene acceso de lectura a ese secreto.
- La clave pública del navegador solo permite Maps JavaScript y está restringida
  a `https://optimapper.vercel.app/*` y a los orígenes locales de Vite.
- Ningún valor de clave se debe guardar en Git ni en esta documentación.
- `ALLOWED_ORIGINS=https://optimapper.vercel.app` limita CORS al frontend desplegado.
  CORS no sustituye a la autenticación ni a las cuotas del servidor.

`.gcloudignore` y `.dockerignore` excluyen entornos virtuales, archivos `.env`,
credenciales y pruebas de la imagen de producción.

## Almacenamiento de imágenes

Se eliminaron seis imágenes antiguas sin referencias de revisiones de Cloud Run,
con autorización del propietario. Se conservaron la imagen que estaba en servicio
y la de la revisión anterior para permitir volver atrás. La liberación efectiva
de capas compartidas puede no coincidir con la suma de tamaños de las imágenes.

Artifact Registry tiene un cupo gratuito de 0,5 GiB por cuenta. Conservar imágenes,
código fuente de builds y otros recursos puede generar costes de almacenamiento
aunque Cloud Run esté escalado a cero. El corte de Cloud Run no limita esos costes.

## Desplegar

Antes de desplegar, ejecutar las pruebas y registrar el commit. Construir el
backend desde `backend/`, conservar las variables existentes y añadir el secreto
con `--update-secrets`, nunca con una sustitución completa de la configuración.
Usar primero una revisión sin tráfico y una etiqueta de prueba; comprobar el
esquema de la API y un itinerario real antes de enviar tráfico de producción.

El script `infra/deploy-backend.ps1` construye la imagen con un worker `e2-medium`,
etiqueta el commit y crea esa revisión de prueba. Configura una instancia máxima,
cero mínimas, 512 MiB, dos solicitudes concurrentes, CORS para el frontend y las
sugerencias de Claude desactivadas. Mantiene el resto de variables existentes.

La nueva interfaz debe publicarse antes de activar Places en el backend de
producción: la interfaz anterior usa Leaflet y no debe representar datos de Google
en el mapa de OpenStreetMap.

## Validación del 25 de octubre de 2026

- Backend candidato: `optimapper-api-00013-jaj`, commit
  `c1d41c616cb46e1a5f1715db0df25ca1f042aca6`.
- URL de prueba: `https://candidate---optimapper-api-x35lojuy3a-ew.a.run.app`.
- La revisión `optimapper-api-00011-qfq` conserva el 100 % del tráfico de producción
  mientras falta publicar la interfaz correspondiente en Vercel.
- Pasan 31 pruebas de backend y 11 de frontend; la compilación de producción del
  frontend y la construcción de la imagen de Python 3.11 completaron correctamente.
- Prueba real: Madrid, 2 días desde el 2 de noviembre de 2026, 8 horas diarias,
  desplazamientos a pie y Claude desactivado. Resultado: 4 y 5 visitas, con
  472 y 430 minutos totales por día; los trayectos elegidos tienen datos de Routes.
- Se comprobó el guardado en Supabase con esquema de itinerario versión 2 y sin
  coordenadas originales de Google persistidas, y la preflight CORS del dominio de Vercel.
- La validación con datos reales motivó excluir municipios vecinos que caían
  dentro del círculo de búsqueda y evitar reservar un día a un único punto lejano
  cuando hay zonas con varias visitas disponibles.
- Vercel compiló la rama como Preview. La publicación en el dominio de producción
  y las variables de Maps requieren autorizar la integración de Vercel.

Una vez publicado ese frontend y configurada su clave pública, se puede activar
la revisión ya validada sin construir otra imagen:

```powershell
gcloud run services update-traffic optimapper-api --region=europe-west1 --project=optimapper-489016 --to-revisions=optimapper-api-00013-jaj=100
```

Referencias: [cuotas de Maps](https://developers.google.com/maps/reporting-and-monitoring/reporting),
[spend caps de Cloud Run](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
[precios de Artifact Registry](https://cloud.google.com/artifact-registry/pricing).
