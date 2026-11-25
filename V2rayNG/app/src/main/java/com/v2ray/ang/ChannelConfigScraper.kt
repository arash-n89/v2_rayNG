package com.example.collector

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.jsoup.Jsoup

/**
 * Dependencies (app/build.gradle):
 *   implementation("com.squareup.okhttp3:okhttp:4.12.0")
 *   implementation("org.jsoup:jsoup:1.17.2")
 *   implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
 *
 * Pass an OkHttpClient with a proxy set if t.me is blocked on your network.
 */
class ChannelConfigScraper(
    private val client: OkHttpClient = OkHttpClient()
) {
    private val linkRegex = Regex(
        """(?:vless|vmess|trojan|ss|hysteria2|hy2|tuic)://[^\s<>"'`]+""",
        RegexOption.IGNORE_CASE
    )

    /** Fetch several channels in parallel; returns de-duplicated config links. */
    suspend fun scrapeAll(channels: List<String>, pages: Int = 3): List<String> =
        coroutineScope {
            channels
                .map { ch -> async { runCatching { scrapeChannel(ch, pages) }.getOrDefault(emptyList()) } }
                .awaitAll()
                .flatten()
                .distinct()
        }

    /** Scrape one public channel, going back `pages` pages (~20 posts each). */
    suspend fun scrapeChannel(channel: String, pages: Int = 3): List<String> =
        withContext(Dispatchers.IO) {
            val name = channel.trim().removePrefix("@").substringAfterLast("/")
            val found = LinkedHashSet<String>()
            var before: Long? = null

            repeat(pages) {
                val url = buildString {
                    append("https://t.me/s/").append(name)
                    if (before != null) append("?before=").append(before)
                }
                val html = fetch(url) ?: return@withContext found.toList()
                val doc = Jsoup.parse(html)

                doc.select(".tgme_widget_message_text").forEach { el ->
                    linkRegex.findAll(el.text()).forEach { found.add(clean(it.value)) }
                }

                // oldest message id on this page -> next page
                val ids = doc.select("[data-post]").mapNotNull {
                    it.attr("data-post").substringAfterLast("/").toLongOrNull()
                }
                val oldest = ids.minOrNull() ?: return@withContext found.toList()
                if (oldest == before) return@withContext found.toList()
                before = oldest
            }
            found.toList()
        }

    private fun fetch(url: String): String? {
        val req = Request.Builder()
            .url(url)
            .header("User-Agent", "Mozilla/5.0 (Android 14; Mobile)")
            .build()
        client.newCall(req).execute().use { r ->
            return if (r.isSuccessful) r.body?.string() else null
        }
    }

    // strip trailing punctuation that often sticks to links in posts
    private fun clean(s: String) = s.trimEnd('.', ',', ';', ')', ']', '،')
}
