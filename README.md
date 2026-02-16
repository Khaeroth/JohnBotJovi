# JohnBotJovi

Bot musical para Discord que reproduce audio desde YouTube y soporta enlaces de Spotify (resolviéndolos a búsquedas de YouTube).

## Requisitos

- Python 3.10+
- Una aplicación de Discord con token de bot
- (Opcional) Credenciales de Spotify para soporte de enlaces Spotify
- **FFmpeg instalado correctamente**

## Instalación local (Windows) con `ffmpeg.exe` en la raíz

> Este proyecto está preparado para buscar FFmpeg en este orden:
> 1. Variable `FFMPEG_PATH` en `.env`
> 2. Archivo `ffmpeg.exe` en la raíz del proyecto
> 3. Archivo `ffmpeg` en la raíz del proyecto
> 4. FFmpeg disponible en `PATH`

### 1) Clona el repositorio

```bash
git clone <URL_DEL_REPO>
cd JohnBotJovi
```

### 2) Crea y activa entorno virtual

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3) Instala dependencias

```bash
pip install -r requirements.txt
```

### 4) Descarga FFmpeg y deja `ffmpeg.exe` en la raíz

1. Descarga un build de FFmpeg para Windows (zip) desde una fuente confiable.
2. Descomprime el archivo.
3. Ubica `ffmpeg.exe` (normalmente dentro de una carpeta `bin`).
4. Copia **solo** `ffmpeg.exe` y pégalo en la raíz del proyecto, al mismo nivel que `bot.py`.

Estructura esperada:

```text
JohnBotJovi/
├─ bot.py
├─ ffmpeg.exe   <-- aquí
├─ .env
├─ cogs/
└─ ...
```

### 5) Crea tu `.env`

```bash
copy .env.example .env
```

Luego edita `.env` y completa `DISCORD_TOKEN` (y Spotify si lo usarás).

### 6) Ejecuta el bot

```bash
python bot.py
```

## Variables de entorno

Ver `.env.example` para la plantilla completa.

- `DISCORD_TOKEN` (obligatoria): token del bot de Discord.
- `SPOTIFY_CLIENT_ID` (opcional): client id de Spotify.
- `SPOTIFY_CLIENT_SECRET` (opcional): client secret de Spotify.
- `FFMPEG_PATH` (opcional): ruta explícita al binario de FFmpeg. Si no se define, se intentará usar `./ffmpeg.exe`.


## Cómo obtener credenciales de Spotify (`SPOTIFY_CLIENT_ID` y `SPOTIFY_CLIENT_SECRET`)

1. Entra a [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) e inicia sesión.
2. Haz clic en **Create app**.
3. Completa nombre y descripción de la app (puede ser algo como `JohnBotJovi`).
4. Acepta los términos y crea la app.
5. Dentro de la app, copia:
   - **Client ID** → úsalo como `SPOTIFY_CLIENT_ID`
   - **Client Secret** (botón *View client secret*) → úsalo como `SPOTIFY_CLIENT_SECRET`
6. Pega ambos valores en tu archivo `.env`.

Ejemplo:

```env
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
```

> Nota: para este bot no necesitas flujo OAuth de usuario; basta con credenciales de aplicación para resolver metadata de canciones/listas.

## Docker

Se incluye `Dockerfile` y `docker-compose.yml`.

### Ejecutar con Docker Compose

1. Crea tu `.env` a partir de `.env.example`.
2. Levanta el servicio:

```bash
docker compose up -d --build
```

3. Ver logs:

```bash
docker compose logs -f
```

> En Docker **no necesitas** `ffmpeg.exe` de Windows, porque la imagen instala FFmpeg para Linux.

## Comando de diagnóstico

El bot incluye `/musicdiag` para comprobar, entre otras cosas, qué ruta/versión de FFmpeg está detectando en runtime.

## Licencia

MIT.
