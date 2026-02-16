\# JohnBotJovi



Bot musical para Discord que reproduce audio desde YouTube y soporta enlaces de Spotify (resolviéndolos a búsquedas de YouTube).



\## Requisitos



\- Python 3.10+

\- Una aplicación de Discord con token de bot

\- (Opcional) Credenciales de Spotify para soporte de enlaces Spotify

\- \*\*FFmpeg instalado correctamente\*\*



\## Instalación local (Windows) con `ffmpeg.exe` en la raíz



> Este proyecto está preparado para buscar FFmpeg en este orden:

> 1. Variable `FFMPEG\_PATH` en `.env`

> 2. Archivo `ffmpeg.exe` en la raíz del proyecto

> 3. Archivo `ffmpeg` en la raíz del proyecto

> 4. FFmpeg disponible en `PATH`



\### 1) Clona el repositorio



```bash

git clone <URL\_DEL\_REPO>

cd JohnBotJovi

```



\### 2) Crea y activa entorno virtual



```bash

python -m venv .venv

.venv\\Scripts\\activate

```



\### 3) Instala dependencias



```bash

pip install -r requirements.txt

```



\### 4) Descarga FFmpeg y deja `ffmpeg.exe` en la raíz



1\. Descarga un build de FFmpeg para Windows (zip) desde una fuente confiable.

2\. Descomprime el archivo.

3\. Ubica `ffmpeg.exe` (normalmente dentro de una carpeta `bin`).

4\. Copia \*\*solo\*\* `ffmpeg.exe` y pégalo en la raíz del proyecto, al mismo nivel que `bot.py`.



Estructura esperada:



```text

JohnBotJovi/

├─ bot.py

├─ ffmpeg.exe   <-- aquí

├─ .env

├─ cogs/

└─ ...

```



\### 5) Crea tu `.env`



```bash

copy .env.example .env

```



Luego edita `.env` y completa `DISCORD\_TOKEN` (y Spotify si lo usarás).



\### 6) Ejecuta el bot



```bash

python bot.py

```



\## Variables de entorno



Ver `.env.example` para la plantilla completa.



\- `DISCORD\_TOKEN` (obligatoria): token del bot de Discord.

\- `SPOTIFY\_CLIENT\_ID` (opcional): client id de Spotify.

\- `SPOTIFY\_CLIENT\_SECRET` (opcional): client secret de Spotify.

\- `FFMPEG\_PATH` (opcional): ruta explícita al binario de FFmpeg. Si no se define, se intentará usar `./ffmpeg.exe`.





\## Cómo obtener credenciales de Spotify (`SPOTIFY\_CLIENT\_ID` y `SPOTIFY\_CLIENT\_SECRET`)



1\. Entra a \[Spotify Developer Dashboard](https://developer.spotify.com/dashboard) e inicia sesión.

2\. Haz clic en \*\*Create app\*\*.

3\. Completa nombre y descripción de la app (puede ser algo como `JohnBotJovi`).

4\. Acepta los términos y crea la app.

5\. Dentro de la app, copia:

&nbsp;  - \*\*Client ID\*\* → úsalo como `SPOTIFY\_CLIENT\_ID`

&nbsp;  - \*\*Client Secret\*\* (botón \*View client secret\*) → úsalo como `SPOTIFY\_CLIENT\_SECRET`

6\. Pega ambos valores en tu archivo `.env`.



Ejemplo:



```env

SPOTIFY\_CLIENT\_ID=tu\_client\_id

SPOTIFY\_CLIENT\_SECRET=tu\_client\_secret

```



> Nota: para este bot no necesitas flujo OAuth de usuario; basta con credenciales de aplicación para resolver metadata de canciones/listas.



\## Docker



Se incluye `Dockerfile` y `docker-compose.yml`.



\### Ejecutar con Docker Compose



1\. Crea tu `.env` a partir de `.env.example`.

2\. Levanta el servicio:



```bash

docker compose up -d --build

```



3\. Ver logs:



```bash

docker compose logs -f

```



> En Docker \*\*no necesitas\*\* `ffmpeg.exe` de Windows, porque la imagen instala FFmpeg para Linux.





\### Deploy en Portainer (Raspberry Pi / Docker Stack)



Si te aparece este error:



```text

failed to resolve services environment: env file .../.env not found

```



significa que el stack intentó cargar un archivo `.env` que no existe en el host de Portainer.



Con la versión actual de `docker-compose.yml` \*\*ya no se requiere `env\_file`\*\*.

Solo debes definir variables en el propio stack de Portainer:



1\. En Portainer, abre tu stack.

2\. Ve a \*\*Environment variables\*\*.

3\. Agrega al menos:

&nbsp;  - `DISCORD\_TOKEN` (obligatoria)

4\. Opcionalmente agrega:

&nbsp;  - `SPOTIFY\_CLIENT\_ID`

&nbsp;  - `SPOTIFY\_CLIENT\_SECRET`

&nbsp;  - `FFMPEG\_PATH`

5\. Redeploy del stack.



> Recomendación para Raspberry Pi: usa imagen/base multi-arquitectura (como `python:3.12-slim`, ya usada en este repo) y evita montar volúmenes del código en producción.



\## Comando de diagnóstico



El bot incluye `/musicdiag` para comprobar, entre otras cosas, qué ruta/versión de FFmpeg está detectando en runtime.



\## Licencia



MIT.

