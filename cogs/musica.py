import asyncio
import logging
import os
import random
import shutil
import subprocess
import urllib.parse

import discord
import spotipy
import yt_dlp
from discord import option
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials
from yt_dlp.utils import DownloadError

log = logging.getLogger("musica")

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": False,
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

YTDL_STREAM_PRIMARY_OPTIONS = {
    **YTDL_OPTIONS,
    "noplaylist": True,
    "extractor_args": {"youtube": {"player_client": ["ios", "android", "web"]}},
}

YTDL_STREAM_FALLBACK_OPTIONS = {
    **YTDL_OPTIONS,
    "noplaylist": True,
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn",
}


def create_youtube_search_query(artist, title):
    return f"{artist} - {title}"


def format_duration(seconds):
    if not seconds or seconds <= 0:
        return "?:??"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_time_to_seconds(raw_time):
    """Convierte '90', '1:30' o '01:02:03' a segundos."""
    value = (raw_time or "").strip()
    if not value:
        raise ValueError("Tiempo vacío")

    if value.isdigit():
        return int(value)

    parts = value.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Formato inválido")

    try:
        nums = [int(p) for p in parts]
    except ValueError as exc:
        raise ValueError("Formato inválido") from exc

    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds

    hours, minutes, seconds = nums
    return hours * 3600 + minutes * 60 + seconds


def normalize_entry_url(entry):
    if not entry:
        return None

    url = entry.get("webpage_url") or entry.get("url")
    if not url:
        return None

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if isinstance(url, str) and url.startswith("/"):
        return f"https://www.youtube.com{url}"

    if isinstance(url, str) and len(url) >= 10 and " " not in url and "/" not in url and "?" not in url:
        return f"https://www.youtube.com/watch?v={url}"

    return None


def is_likely_url(value):
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def should_force_youtube_search(value):
    if not is_likely_url(value):
        return True

    host = urllib.parse.urlparse(value).netloc.lower()
    allowed_hosts = ("youtube.com", "youtu.be", "music.youtube.com")
    return not any(h in host for h in allowed_hosts)


def make_extraction_query(raw_query):
    if should_force_youtube_search(raw_query):
        return f"ytsearch1:{raw_query}"
    return raw_query


def is_youtube_url(value):
    if not is_likely_url(value):
        return False
    host = urllib.parse.urlparse(value).netloc.lower()
    return any(h in host for h in ("youtube.com", "youtu.be", "music.youtube.com"))


def extract_stream_info(url, primary, fallback):
    try:
        return primary.extract_info(url, download=False)
    except DownloadError as e1:
        log.warning(f"Fallo extracción primaria para {url}: {e1}")
        return fallback.extract_info(url, download=False)


class Musica(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current_song = {}
        self.default_volume = 0.05
        self.disconnect_timer = {}
        self.guild_locks = {}
        self.max_queue_size = 300

        self.ytdl_stream_primary = yt_dlp.YoutubeDL(YTDL_STREAM_PRIMARY_OPTIONS)
        self.ytdl_stream_fallback = yt_dlp.YoutubeDL(YTDL_STREAM_FALLBACK_OPTIONS)

        spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.spotify_client = None

        if spotify_client_id and spotify_client_secret:
            try:
                spotify_auth_manager = SpotifyClientCredentials(
                    client_id=spotify_client_id,
                    client_secret=spotify_client_secret,
                )
                self.spotify_client = spotipy.Spotify(auth_manager=spotify_auth_manager)
                log.info("🌐 Cliente de Spotify inicializado en el cog de música.")
            except Exception as e:
                log.error("⚠️ Error al inicializar el cliente de Spotify en musica.py.")
                log.exception(e)
        else:
            log.warning("🚫 Credenciales de Spotify no encontradas. Spotify deshabilitado.")

    # ----------------------------
    # Helpers de diseño/mantenimiento
    # ----------------------------
    def get_queue(self, server_id):
        server_id = str(server_id)
        if server_id not in self.queues:
            self.queues[server_id] = []
        return self.queues[server_id]

    def get_lock(self, server_id):
        server_id = str(server_id)
        if server_id not in self.guild_locks:
            self.guild_locks[server_id] = asyncio.Lock()
        return self.guild_locks[server_id]

    def song_label(self, song):
        return f"{song['titulo']} [{format_duration(song.get('duration'))}]"

    def build_song(self, *, webpage_url, titulo, channel_id, duration, requested_by=None):
        return {
            "url": webpage_url,
            "webpage_url": webpage_url,
            "titulo": titulo or "Desconocido",
            "duration": duration or 0,
            "channel_id": channel_id,
            "requested_by": requested_by,
        }

    async def safe_send(self, channel_id, content):
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(content)
        except Exception as e:
            log.warning(f"No se pudo enviar mensaje al canal {channel_id}: {e}")

    async def extract_info_async(self, query, timeout=25):
        fut = self.bot.loop.run_in_executor(None, lambda q=query: ytdl.extract_info(q, download=False))
        return await asyncio.wait_for(fut, timeout=timeout)

    async def resolve_stream_with_retry(self, source_query, retries=2):
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                fut = self.bot.loop.run_in_executor(
                    None,
                    lambda q=source_query: extract_stream_info(q, self.ytdl_stream_primary, self.ytdl_stream_fallback),
                )
                info = await asyncio.wait_for(fut, timeout=25)
                if info and info.get("url"):
                    return info
                last_error = ValueError("Stream sin URL")
            except Exception as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(0.6)
        raise last_error or ValueError("No se pudo resolver stream")

    # ----------------------------
    # Auto-desconexión
    # ----------------------------
    async def start_disconnect_timer(self, server_id, channel_id):
        self.cancel_disconnect_timer(server_id)
        self.disconnect_timer[str(server_id)] = self.bot.loop.create_task(
            self.run_disconnect_timer(str(server_id), channel_id)
        )

    def cancel_disconnect_timer(self, server_id):
        server_id = str(server_id)
        if server_id in self.disconnect_timer:
            self.disconnect_timer[server_id].cancel()
            del self.disconnect_timer[server_id]

    async def run_disconnect_timer(self, server_id, channel_id):
        try:
            await asyncio.sleep(300)
            guild = self.bot.get_guild(int(server_id))
            if guild and guild.voice_client:
                vc = guild.voice_client
                if not vc.is_playing() and not vc.is_paused():
                    await vc.disconnect()
                    self.cancel_disconnect_timer(server_id)
                    await self.safe_send(channel_id, "😴 Desconectado automáticamente por inactividad (5 minutos).")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error en run_disconnect_timer: {e}")

    # ----------------------------
    # Cola y reproducción
    # ----------------------------
    def parse_removal_indices(self, cola_length, input_str):
        indices_to_remove = set()
        for part in input_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    start, end = map(int, part.split("-"))
                    for i in range(start, end + 1):
                        indices_to_remove.add(i)
                except ValueError:
                    continue
            else:
                try:
                    indices_to_remove.add(int(part))
                except ValueError:
                    continue

        return sorted([i - 1 for i in indices_to_remove if 1 <= i <= cola_length], reverse=True)

    async def on_song_end(self, server_id, error):
        if error:
            # Skip/Stop pueden generar cierre esperado de ffmpeg en algunos entornos.
            log.warning(f"Finalizó canción con detalle: {error}")
        await self.play_next(server_id)

    async def play_next(self, server_id):
        server_id = str(server_id)
        lock = self.get_lock(server_id)

        async with lock:
            guild = self.bot.get_guild(int(server_id))
            if not guild:
                return

            vc = guild.voice_client
            if vc is None:
                self.queues.get(server_id, []).clear()
                return

            if vc.is_playing() or vc.is_paused():
                return

            if not self.queues.get(server_id):
                self.current_song.pop(server_id, None)
                if vc.channel:
                    self.bot.loop.create_task(self.start_disconnect_timer(server_id, vc.channel.id))
                return

            self.cancel_disconnect_timer(server_id)

            next_item = self.queues[server_id].pop(0)
            self.current_song[server_id] = next_item

            try:
                source_query = next_item.get("webpage_url") or next_item.get("url")
                if not source_query:
                    raise ValueError("Canción sin URL de origen.")

                fresh_info = await self.resolve_stream_with_retry(source_query, retries=2)
                url_stream = fresh_info.get("url")
                if not url_stream:
                    raise ValueError("No se obtuvo URL de stream reproducible.")

                source = discord.FFmpegPCMAudio(url_stream, **FFMPEG_OPTIONS)
                source = discord.PCMVolumeTransformer(source, volume=self.default_volume)

                log.info("🎵 Stream listo: %s | extractor=%s", self.song_label(next_item), fresh_info.get("extractor"))

                def next_song(error):
                    self.bot.loop.create_task(self.on_song_end(server_id, error))

                vc.play(source, after=next_song)
                await self.safe_send(next_item["channel_id"], f"▶️ Reproduciendo: **{self.song_label(next_item)}**")

            except Exception as e:
                log.error(f"Error preparando canción {self.song_label(next_item)}: {e}", exc_info=True)
                await self.safe_send(next_item["channel_id"], f"⚠️ No se pudo reproducir: **{self.song_label(next_item)}**")
                self.bot.loop.create_task(self.play_next(server_id))

    # ----------------------------
    # Comandos
    # ----------------------------
    @discord.slash_command(description="Busca y reproduce música (o añade a la cola).")
    @option("busqueda", str, description="URL o nombre de la canción.")
    async def play(self, ctx, busqueda: str):
        await ctx.defer()

        if not ctx.author.voice:
            return await ctx.followup.send("🚫 Debes estar en un canal de voz.", ephemeral=False)

        canal_usuario = ctx.author.voice.channel
        vc = None

        try:
            for attempt in range(1, 3):
                vc = ctx.voice_client
                try:
                    if vc is None or not vc.is_connected():
                        vc = await canal_usuario.connect(timeout=60, reconnect=True)
                    elif vc.channel.id != canal_usuario.id:
                        await vc.move_to(canal_usuario)
                    break
                except IndexError:
                    log.warning(f"⚠️ Reintento {attempt} por IndexError...")
                    if vc and vc.is_connected():
                        try:
                            await vc.disconnect(force=True)
                        except Exception:
                            pass
                    await asyncio.sleep(3)
                    if attempt == 2:
                        raise

            await asyncio.sleep(0.3)
            await ctx.followup.edit_message(message_id="@original", content=f"🔎 Buscando: `{busqueda}`...")

            songs_to_process = []
            is_spotify_source = False
            playlist_title = "Búsqueda Directa"

            if "spotify.com" in busqueda and not self.spotify_client:
                await ctx.followup.edit_message(
                    message_id="@original",
                    content="⚠️ Enlace Spotify detectado, pero faltan SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET.",
                )
                return

            if "spotify.com" in busqueda and self.spotify_client:
                is_spotify_source = True
                parsed_url = urllib.parse.urlparse(busqueda)
                path_segments = [p for p in parsed_url.path.split("/") if p]

                entity_type = path_segments[0] if len(path_segments) >= 1 else None
                entity_id = path_segments[1].split("?")[0] if len(path_segments) >= 2 else None

                try:
                    if entity_type == "track":
                        track = self.spotify_client.track(entity_id)
                        artist = track["artists"][0]["name"]
                        title = track["name"]
                        songs_to_process.append(create_youtube_search_query(artist, title))
                        playlist_title = f"Canción Spotify: {title}"
                    elif entity_type == "playlist":
                        playlist_metadata = self.spotify_client.playlist(entity_id)
                        playlist_title = playlist_metadata.get("name", "Playlist Spotify")
                        playlist_tracks = self.spotify_client.playlist_items(entity_id, limit=50)
                        for item in playlist_tracks.get("items", []):
                            track = item.get("track") if item else None
                            if track and track.get("name") and track.get("artists"):
                                artist = track["artists"][0]["name"]
                                title = track["name"]
                                songs_to_process.append(create_youtube_search_query(artist, title))
                    else:
                        await ctx.followup.edit_message(
                            message_id="@original",
                            content="⚠️ Enlace Spotify no reconocido (solo track/playlist).",
                        )
                        return
                except Exception as e:
                    log.error(f"Error al procesar Spotify: {e}")
                    await ctx.followup.edit_message(
                        message_id="@original",
                        content="⚠️ Error al procesar el enlace de Spotify.",
                    )
                    return
            else:
                songs_to_process.append(busqueda)

            server_id = str(ctx.guild.id)
            self.cancel_disconnect_timer(server_id)
            queue = self.get_queue(server_id)

            songs_to_add = []
            max_songs = min(150, max(0, self.max_queue_size - len(queue)))
            if max_songs == 0:
                await ctx.followup.edit_message(
                    message_id="@original",
                    content=f"⚠️ La cola alcanzó su límite ({self.max_queue_size} canciones).",
                )
                return

            for search_query in songs_to_process:
                if len(songs_to_add) >= max_songs:
                    break
                try:
                    info = await self.extract_info_async(make_extraction_query(search_query), timeout=25)
                    if not info:
                        continue

                    if "entries" in info and info.get("entries"):
                        if not is_spotify_source:
                            playlist_title = info.get("title", playlist_title)

                        for entry in info["entries"]:
                            if len(songs_to_add) >= max_songs:
                                break
                            try:
                                url_to_fetch = normalize_entry_url(entry)
                                if not url_to_fetch or not is_youtube_url(url_to_fetch):
                                    continue
                                titulo = entry.get("title", "Desconocido")
                                duration = entry.get("duration") or 0
                                songs_to_add.append(
                                    self.build_song(
                                        webpage_url=url_to_fetch,
                                        titulo=titulo,
                                        duration=duration,
                                        channel_id=ctx.channel.id,
                                        requested_by=ctx.author.id,
                                    )
                                )
                            except Exception as song_e:
                                log.warning(f"⚠️ Se saltó una canción ({url_to_fetch}). Error: {song_e}")
                                continue
                    else:
                        if info.get("_type") == "playlist" and info.get("entries"):
                            info = info["entries"][0]

                        webpage = normalize_entry_url(info)
                        if not webpage or not is_youtube_url(webpage):
                            continue

                        songs_to_add.append(
                            self.build_song(
                                webpage_url=webpage,
                                titulo=info.get("title", "Desconocido"),
                                duration=info.get("duration") or 0,
                                channel_id=ctx.channel.id,
                                requested_by=ctx.author.id,
                            )
                        )
                except Exception as e:
                    log.warning(f"No se pudo extraer para: {search_query}. Error: {e}")
                    continue

            if not songs_to_add:
                return await ctx.followup.edit_message(
                    message_id="@original", content="⚠️ No se encontraron canciones válidas para reproducir."
                )

            queue.extend(songs_to_add)
            total_secs = sum((s.get("duration") or 0) for s in songs_to_add)

            if len(songs_to_add) > 1:
                msg = (
                    f"🎶 **{len(songs_to_add)}** canciones de **{playlist_title}** añadidas "
                    f"({format_duration(total_secs)} en total)."
                )
                if len(songs_to_add) >= max_songs:
                    msg += f" (Se limitó a {max_songs} canciones)."
                pos_start = len(queue) - len(songs_to_add) + 1
            else:
                msg = f"🎶 **{self.song_label(songs_to_add[0])}** añadida a la cola."
                pos_start = len(queue)

            if not vc.is_playing() and not vc.is_paused():
                await self.play_next(server_id)
                msg += " Iniciando reproducción."
            else:
                msg += f" (Comienza en posición #{pos_start})."

            await ctx.followup.edit_message(message_id="@original", content=msg)

        except Exception as e:
            log.error(f"Error en /play: {e}", exc_info=True)
            await ctx.followup.send(f"⚠️ Error al reproducir. ({type(e).__name__})", ephemeral=False)

    @discord.slash_command(description="Baraja la cola de reproducción.")
    async def shuffle(self, ctx):
        server_id = str(ctx.guild.id)
        cola = self.get_queue(server_id)

        if len(cola) < 2:
            return await ctx.respond("⚠️ Necesitas al menos 2 canciones en cola para barajar.", ephemeral=False)

        random.shuffle(cola)
        await ctx.respond("🔀 **¡Cola barajada!**", ephemeral=False)

    @discord.slash_command(description="Mueve una canción de posición dentro de la cola.")
    @option("origen", int, description="Posición actual (1..N).", min_value=1)
    @option("destino", int, description="Nueva posición (1..N).", min_value=1)
    async def move(self, ctx, origen: int, destino: int):
        server_id = str(ctx.guild.id)
        cola = self.get_queue(server_id)
        if not cola:
            return await ctx.respond("📭 La cola está vacía.", ephemeral=False)
        if origen > len(cola) or destino > len(cola):
            return await ctx.respond(f"⚠️ Las posiciones deben estar entre 1 y {len(cola)}.", ephemeral=False)

        song = cola.pop(origen - 1)
        cola.insert(destino - 1, song)
        await ctx.respond(f"↕️ Movida: **{self.song_label(song)}** a posición #{destino}.", ephemeral=False)

    @discord.slash_command(description="Quita canciones de la cola por número, rangos (3-5) o comas (2,4,6).")
    @option("numero", str, description="Números o rangos (ej: '3', '2-5', '1,4').")
    async def remove(self, ctx, numero: str):
        server_id = str(ctx.guild.id)
        cola = self.get_queue(server_id)
        cola_length = len(cola)

        if cola_length == 0:
            return await ctx.respond("📭 La cola está vacía.", ephemeral=False)

        indices_to_remove = self.parse_removal_indices(cola_length, numero)
        if not indices_to_remove:
            return await ctx.respond(
                f"⚠️ Formato inválido o números fuera de rango (1 a {cola_length}).",
                ephemeral=False,
            )

        removed = []
        for idx in indices_to_remove:
            removed.append(self.song_label(cola.pop(idx)))

        if len(removed) == 1:
            await ctx.respond(f"🗑️ Eliminada: **{removed[0]}**")
        else:
            await ctx.respond(f"🗑️ Eliminadas **{len(removed)}** canciones de la cola.")

    @discord.slash_command(description="Salta a la siguiente canción de la cola.")
    async def skip(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond("🚫 El bot no está conectado.", ephemeral=False)

        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await ctx.respond("⏭️ Canción saltada.", ephemeral=False)
        else:
            await ctx.respond("🎶 No hay música sonando para saltar.", ephemeral=False)

    @discord.slash_command(description="Detiene la música, borra la cola y desconecta.")
    async def stop(self, ctx):
        vc = ctx.voice_client
        server_id = str(ctx.guild.id)

        if vc:
            self.cancel_disconnect_timer(server_id)
            self.get_queue(server_id).clear()
            self.current_song.pop(server_id, None)
            vc.stop()
            await vc.disconnect()
            await ctx.respond("🛑 Música detenida. Bot desconectado.", ephemeral=False)
        else:
            await ctx.respond("🚫 No hay música en reproducción.", ephemeral=False)

    @discord.slash_command(description="Pausa la canción actual.")
    async def pause(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond("🚫 El bot no está conectado al canal de voz.", ephemeral=False)

        if vc.is_playing():
            vc.pause()
            await ctx.respond("⏸️ Música pausada.", ephemeral=False)
        elif vc.is_paused():
            await ctx.respond("Ya estaba pausado.", ephemeral=True)
        else:
            await ctx.respond("🎶 No hay música sonando para pausar.", ephemeral=False)

    @discord.slash_command(description="Reanuda la canción pausada.")
    async def resume(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            return await ctx.respond("🚫 El bot no está conectado al canal de voz.", ephemeral=False)

        if vc.is_paused():
            vc.resume()
            await ctx.respond("▶️ Música reanudada.", ephemeral=False)
        elif vc.is_playing():
            await ctx.respond("La música ya estaba sonando.", ephemeral=True)
        else:
            await ctx.respond("🎶 No hay música pausada para reanudar.", ephemeral=False)

    @discord.slash_command(description="Muestra la cola de reproducción.")
    async def queue(self, ctx):
        server_id = str(ctx.guild.id)
        cola = self.get_queue(server_id)

        if not cola:
            return await ctx.respond(":man_shrugging: La cola está vacía.", ephemeral=False)

        total_secs = sum((song.get("duration") or 0) for song in cola)
        txt = f"**📜 Cola de Reproducción ({len(cola)} canciones · {format_duration(total_secs)}):**\n"
        for i, song in enumerate(cola):
            if i >= 20:
                txt += f"\n*...y {len(cola) - 20} más.*"
                break
            txt += f"**{i + 1}.** {self.song_label(song)}\n"

        await ctx.respond(txt)

    @discord.slash_command(description="Borra todas las canciones de la cola.")
    async def clear(self, ctx):
        server_id = str(ctx.guild.id)
        queue = self.get_queue(server_id)
        if queue:
            queue.clear()
            await ctx.respond("🗑️ La cola ha sido vaciada.", ephemeral=False)
        else:
            await ctx.respond("📭 La cola ya estaba vacía.", ephemeral=False)

    @discord.slash_command(name="volume", description="Ajusta el volumen (0-100).")
    @option("nivel", int, description="Porcentaje de volumen (0 a 100).", min_value=0, max_value=100)
    async def set_volume(self, ctx, nivel: int):
        vc = ctx.voice_client
        self.default_volume = nivel / 100.0

        if vc and vc.is_playing() and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = self.default_volume
            await ctx.respond(f"🔊 Volumen cambiado a **{nivel}%**.")
        else:
            await ctx.respond(f"🔊 Volumen configurado a **{nivel}%** (se aplicará en la próxima canción).")

    @discord.slash_command(description="Reinicia la canción actual.")
    async def replay(self, ctx):
        server_id = str(ctx.guild.id)
        vc = ctx.voice_client

        if server_id not in self.current_song or not self.current_song[server_id]:
            return await ctx.respond("⚠️ No hay canción registrada sonando.", ephemeral=False)

        if not vc or not vc.is_connected():
            return await ctx.respond("🚫 No estoy conectado.", ephemeral=False)

        current = self.current_song[server_id]
        self.get_queue(server_id).insert(0, current)
        vc.stop()
        await ctx.respond(f"🔄 Reiniciando: **{self.song_label(current)}**", ephemeral=False)

    @discord.slash_command(description="Salta a un tiempo específico de la canción actual (ej: 90, 1:30, 00:02:15).")
    @option("tiempo", str, description="Segundo o formato mm:ss / hh:mm:ss.")
    async def seek(self, ctx, tiempo: str):
        server_id = str(ctx.guild.id)
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.respond("🚫 No estoy conectado a un canal de voz.", ephemeral=False)

        current = self.current_song.get(server_id)
        if not current:
            return await ctx.respond("⚠️ No hay una canción activa para hacer seek.", ephemeral=False)

        try:
            seconds = parse_time_to_seconds(tiempo)
        except ValueError:
            return await ctx.respond("⚠️ Formato inválido. Usa segundos (`90`) o `mm:ss` / `hh:mm:ss`.", ephemeral=False)

        if seconds < 0:
            return await ctx.respond("⚠️ El tiempo no puede ser negativo.", ephemeral=False)

        duration = current.get("duration") or 0
        if duration and seconds >= duration:
            return await ctx.respond(
                f"⚠️ El tiempo solicitado ({format_duration(seconds)}) excede la duración ({format_duration(duration)}).",
                ephemeral=False,
            )

        source_query = current.get("webpage_url") or current.get("url")
        if not source_query:
            return await ctx.respond("⚠️ No se encontró URL de origen para la canción actual.", ephemeral=False)

        try:
            fresh_info = await self.resolve_stream_with_retry(source_query, retries=2)
            url_stream = fresh_info.get("url")
            if not url_stream:
                return await ctx.respond("⚠️ No se pudo resolver el stream para hacer seek.", ephemeral=False)

            seek_options = {
                "before_options": f"-ss {seconds} {FFMPEG_OPTIONS['before_options']}",
                "options": FFMPEG_OPTIONS["options"],
            }
            new_source = discord.FFmpegPCMAudio(url_stream, **seek_options)
            new_source = discord.PCMVolumeTransformer(new_source, volume=self.default_volume)

            # Reemplazar reproducción actual sin alterar la cola.
            vc.stop()

            def next_song(error):
                self.bot.loop.create_task(self.on_song_end(server_id, error))

            vc.play(new_source, after=next_song)

            await ctx.respond(
                f"⏩ Saltando **{self.song_label(current)}** a `{format_duration(seconds)}`.",
                ephemeral=False,
            )
        except Exception as e:
            log.error(f"Error en /seek para {self.song_label(current)}: {e}", exc_info=True)
            await ctx.respond("⚠️ No se pudo realizar seek en la canción actual.", ephemeral=False)

    @discord.slash_command(description="(MOD) Diagnóstico operativo del módulo de música.")
    @discord.default_permissions(administrator=True)
    async def musicdiag(self, ctx):
        ffmpeg_path = shutil.which("ffmpeg") or "no encontrado"
        ffmpeg_ver = "desconocida"
        if ffmpeg_path != "no encontrado":
            try:
                proc = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
                first = (proc.stdout or "").splitlines()
                if first:
                    ffmpeg_ver = first[0]
            except Exception:
                pass

        server_id = str(ctx.guild.id)
        queue_len = len(self.get_queue(server_id))
        msg = (
            f"🩺 Diagnóstico música\n"
            f"- yt-dlp: `{yt_dlp.version.__version__}`\n"
            f"- ffmpeg: `{ffmpeg_path}`\n"
            f"- ffmpeg version: `{ffmpeg_ver}`\n"
            f"- canciones en cola: `{queue_len}`\n"
            f"- volumen por defecto: `{int(self.default_volume * 100)}%`"
        )
        await ctx.respond(msg, ephemeral=True)


def setup(bot):
    bot.add_cog(Musica(bot))
