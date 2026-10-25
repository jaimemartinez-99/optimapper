# Activar Google Maps en OptiMapper

Estos pasos preparan la configuración. No requieren desplegar esta rama sobre
el servicio que ya está en producción.

## 1. Habilitar las APIs

En [Google Cloud Console](https://console.cloud.google.com/), selecciona el proyecto
que utiliza tu servicio de Cloud Run. Comprueba que tiene una cuenta de facturación.
En **APIs y servicios → Biblioteca**, busca y habilita:

- **Places API (New)**: descubre lugares y devuelve coordenadas, horarios y reseñas.
- **Routes API**: proporciona tiempos de desplazamiento. Es opcional si configuras
  `GOOGLE_ROUTES_MAX_ELEMENTS=0`.
- **Maps JavaScript API**: muestra en el frontend los lugares de Google.

No hace falta habilitar Directions API, Distance Matrix API Legacy ni Geocoding API.
La resolución del destino y del alojamiento se hace con Places.

Documentación: [Places](https://developers.google.com/maps/documentation/places/web-service/get-api-key),
[Routes](https://developers.google.com/maps/documentation/routes/get-api-key),
[Maps JavaScript](https://developers.google.com/maps/documentation/javascript/get-api-key).

## 2. Crear claves separadas

En **APIs y servicios → Credenciales → Crear credenciales → Clave de API**:

### Backend

- Ponle un nombre reconocible, por ejemplo `optimapper-backend`.
- En restricciones de API permite únicamente **Places API (New)** y **Routes API**.
- No le apliques restricciones de sitios web: las llamadas salen de Cloud Run.
- Si ya tienes salida por IP estática, restringe la clave a esa IP de salida.
  La dirección/URL pública de Cloud Run no es una IP de salida fija. Configurar
  una IP de salida estática requiere red y Cloud NAT y puede tener coste adicional.
- Guarda la clave en Secret Manager; no la añadas al código ni al frontend.

### Frontend

- Crea otra clave, por ejemplo `optimapper-web`.
- Restricción de aplicación: **Sitios web / HTTP referrers**.
- Añade tu dominio de frontend, por ejemplo `https://tu-dominio.example/*`.
- Para desarrollo añade únicamente los orígenes que uses, por ejemplo
  `http://localhost:5173/*` y `http://127.0.0.1:5173/*`.
- Restricción de API: únicamente **Maps JavaScript API**.
- Esta clave será visible en el navegador; las restricciones forman parte de su configuración.

Puedes crear un Map ID de tipo JavaScript en **Google Maps Platform → Administración
de mapas** y configurarlo como `VITE_GOOGLE_MAP_ID`. En desarrollo se usa `DEMO_MAP_ID`.

Referencia: [seguridad de claves](https://developers.google.com/maps/api-security-best-practices).

## 3. Configurar primero el entorno local

En `backend/.env`, conserva tus variables actuales y añade:

```dotenv
GOOGLE_MAPS_API_KEY=tu_clave_privada_de_backend
GOOGLE_ROUTES_MAX_ELEMENTS=100
```

Con `100` se consultan como máximo 100 pares origen/destino por generación,
recuperación o recálculo. Se priorizan los trayectos del plan preliminar y después
algunas alternativas cercanas. Los trayectos sin datos reales se marcan como estimados.
Con `0` se omite Routes; puedes activar solo Places y Maps para empezar.

En `frontend/.env`:

```dotenv
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_MAPS_API_KEY=tu_clave_publica_restringida_a_la_web
VITE_GOOGLE_MAP_ID=tu_map_id_opcional
```

Reinicia el backend y Vite. En producción, las variables `VITE_*` se incorporan al
**compilar el frontend**, por lo que cambiar únicamente una variable del servidor
después de la compilación no modifica el JavaScript que ya está publicado.

Claude sigue usando `ANTHROPIC_API_KEY`. Si no está disponible y sí hay clave de
Google, el descubrimiento funciona con Places y duraciones orientativas por categoría.

## 4. Preparar Cloud Run

1. Habilita Secret Manager API si todavía no la usas.
2. En **Secret Manager → Crear secreto**, guarda la clave de backend con el nombre
   que elijas, por ejemplo `optimapper-google-maps-key`.
3. Da a la cuenta de servicio que ejecuta Cloud Run el rol **Secret Manager Secret
   Accessor**, limitado a ese secreto.
4. Cuando vayas a desplegar la rama: **Cloud Run → tu servicio → Editar y desplegar
   nueva revisión → Variables y secretos → Referenciar un secreto**. Expón una
   versión concreta como variable `GOOGLE_MAPS_API_KEY`.
5. Añade `GOOGLE_ROUTES_MAX_ELEMENTS=100` como variable normal.
6. Configura el tiempo máximo de solicitud de Cloud Run en al menos 300 segundos.
   La imagen ya usa ese tiempo de espera para Gunicorn.
7. Conserva las referencias existentes de Anthropic y Supabase. No sustituyas el
   conjunto completo de variables al añadir estas dos.
8. Prueba primero una revisión o servicio de staging con el frontend correspondiente.

Usa Supabase para los itinerarios de Cloud Run. La memoria de una instancia se
pierde al reiniciarse y no se comparte con otras instancias. Ejecuta de forma
idempotente `database/sql/create_itineraries_table.sql` para asegurar la columna
`number_of_days`. El JSON nuevo está versionado y los registros antiguos se siguen leyendo.

El fallback público de Nominatim limita solicitudes por proceso. No es adecuado
para múltiples instancias de producción sin un proveedor o limitador compartido.

Referencia: [Secret Manager en Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

## 5. Costes y límites

Precios globales de pago por uso consultados el **25 de octubre de 2026**, en USD,
sin impuestos y para el primer tramo de pago. Los cupos son mensuales y por SKU;
se agregan los proyectos de la misma cuenta de facturación.

| SKU utilizado | Cupo gratuito mensual | Precio por 1.000 después del cupo |
| --- | ---: | ---: |
| Nearby Search Enterprise | 1.000 búsquedas | 35 USD |
| Text Search Enterprise | 1.000 búsquedas | 35 USD |
| Text Search Pro, resolver la ciudad | 5.000 búsquedas | 32 USD |
| Place Details Enterprise, recuperar referencias guardadas | 1.000 consultas | 20 USD |
| Compute Route Matrix Essentials | 10.000 elementos | 5 USD |
| Dynamic Maps | 10.000 cargas | 7 USD |

Los campos de valoración y horarios activan el SKU Enterprise de Places.
"Enterprise" aquí es un nivel de facturación por campos; no exige contratar un plan empresarial.
La implementación no pide reseñas completas, fotos ni resúmenes de IA.

Una generación hace una búsqueda de ciudad, de tres a cinco búsquedas por
categoría y hasta doce búsquedas adicionales de propuestas de Claude. Las
coincidencias ya encontradas evitan esas búsquedas adicionales. Puede haber hasta
diez búsquedas extra de imprescindibles y una de alojamiento.

Ejemplo calculado: 100 generaciones al mes, tres búsquedas Nearby por generación,
entre cero y doce búsquedas Text Search adicionales, hasta 100 elementos de Routes
y una carga de mapa por viaje, **sin reabrir ni recalcular** y sin otro consumo en
la cuenta: aproximadamente **0–7 USD/mes** en Maps. Los 7 USD corresponden a las
200 búsquedas Text Search que excederían su cupo en el caso de 1.200 búsquedas.
Es una estimación aritmética de ese escenario, no una tarifa fija por itinerario.

Agotados los cupos, 100 elementos de matriz cuestan hasta 0,50 USD por operación.
Una matriz completa de 20 × 20 costaría 2 USD; por eso no se consulta N² sin límite.
Reabrir o recalcular también consulta los detalles de cada candidato guardado
(hasta 80, más alojamiento) y vuelve a obtener tiempos. La navegación inmediatamente
después de crear un viaje reutiliza la respuesta en memoria y evita esa segunda consulta.

Claude, Cloud Run, Secret Manager y la infraestructura de red se facturan aparte.
No se incluye ninguna cuota fija de Maps en esta configuración de pago por uso.

En **Facturación → Presupuestos y alertas**, configura un aviso inicial, por ejemplo
10 USD/mes, limitado al proyecto o servicios que quieras vigilar. Un presupuesto
de **solo alertas no corta el gasto**. Reduce también las cuotas disponibles de
cada API desde **APIs y servicios → Cuotas**, y comprueba las unidades de cada cuota.
El límite de la aplicación es por operación, no un límite mensual del proyecto.

Fuentes: [tarifas oficiales](https://developers.google.com/maps/billing-and-pricing/pricing),
[SKU por campos](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing),
[facturación de matrices](https://developers.google.com/maps/documentation/routes/usage-and-billing),
[presupuestos](https://docs.cloud.google.com/billing/docs/how-to/budgets).

## 6. Comprobar la integración

- Genera Madrid para dos o tres días con una fecha, ocho horas diarias y ritmo equilibrado.
- Añade un museo como imprescindible y, si quieres, un alojamiento dentro de la ciudad.
- Comprueba que aparecen horarios, carga diaria, notas y alternativas descartadas.
- Quita una visita o fíjala a otro día y recalcula: se guarda un nuevo itinerario.
- Abre la URL guardada para comprobar la recuperación con Places.
- Revisa el consumo por SKU en Cloud Console antes de aumentar el límite de Routes.

Los horarios futuros/festivos y la duración de cada visita pueden necesitar
confirmación. Esta versión admite caminar y coche; no modela entradas reservadas
con hora fija ni transporte público dependiente de la hora de salida.

Los lugares de Google se muestran en un mapa de Google. Solo se guardan sus
identificadores y las decisiones del plan; los datos de Places se consultan de
nuevo al abrirlo. Revisa las [políticas de Places y condiciones aplicables al EEE](https://developers.google.com/maps/documentation/places/web-service/policies)
antes de publicar una integración nueva.
