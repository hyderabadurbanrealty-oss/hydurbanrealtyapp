using Dapper;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Memory;
using Npgsql;
using System.Text.Json;

namespace HyderabadUrbanReality.Controllers
{
    [ApiController]
    [Route("api/twitter")]
    public class TwitterController : ControllerBase
    {
        private readonly IHttpClientFactory _http;
        private readonly IMemoryCache       _cache;
        private readonly IConfiguration     _config;
        private readonly ILogger<TwitterController> _logger;

        private string ConnStr => _config.GetConnectionString("DefaultConnection")!;
        private const string CacheKey = "social_tweets_oembed";

        public TwitterController(IHttpClientFactory http, IMemoryCache cache,
            IConfiguration config, ILogger<TwitterController> logger)
        {
            _http   = http;
            _cache  = cache;
            _config = config;
            _logger = logger;
        }

        // ── GET /api/twitter/tweets — public, cached ─────────────────────────
        [HttpGet("tweets")]
        [AllowAnonymous]
        public async Task<IActionResult> GetTweets()
        {
            if (_cache.TryGetValue(CacheKey, out List<TweetEmbedDto>? cached))
                return Ok(cached);

            await using var conn = new NpgsqlConnection(ConnStr);
            var urls = (await conn.QueryAsync<SocialTweetRecord>(
                "SELECT id, url, label, is_active, sort_order FROM social_tweets WHERE is_active = TRUE ORDER BY sort_order ASC, created_at DESC"
            )).ToList();

            if (!urls.Any()) return Ok(new List<TweetEmbedDto>());

            var client  = _http.CreateClient("twitter-oembed");
            var results = new List<TweetEmbedDto>();

            foreach (var tweet in urls)
            {
                try
                {
                    var oembedUrl = "https://publish.twitter.com/oembed" +
                                   $"?url={Uri.EscapeDataString(tweet.Url)}" +
                                   "&omit_script=true&hide_thread=true&dnt=true";

                    var response = await client.GetAsync(oembedUrl);
                    if (!response.IsSuccessStatusCode)
                    {
                        _logger.LogWarning("oEmbed 404 for tweet {Url} — invalid or private tweet", tweet.Url);
                        continue;
                    }

                    var json = await response.Content.ReadAsStringAsync();
                    var doc  = JsonDocument.Parse(json);
                    var root = doc.RootElement;

                    results.Add(new TweetEmbedDto(
                        Id:         tweet.Id,
                        Url:        tweet.Url,
                        Label:      tweet.Label ?? "",
                        Html:       root.GetProperty("html").GetString() ?? "",
                        AuthorName: root.TryGetProperty("author_name", out var an) ? an.GetString() ?? "" : ""
                    ));
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to fetch oEmbed for tweet: {Url}", tweet.Url);
                }
            }

            _cache.Set(CacheKey, results, TimeSpan.FromHours(1));
            return Ok(results);
        }

        // ── GET /api/twitter/admin/tweets — admin, full list ─────────────────
        [HttpGet("admin/tweets")]
        [Authorize(Roles = "admin")]
        public async Task<IActionResult> AdminGetAll()
        {
            await using var conn = new NpgsqlConnection(ConnStr);
            var rows = await conn.QueryAsync<SocialTweetRecord>(
                "SELECT * FROM social_tweets ORDER BY sort_order ASC, created_at DESC");
            return Ok(rows);
        }

        // ── POST /api/twitter/admin/tweets — add tweet ───────────────────────
        [HttpPost("admin/tweets")]
        [Authorize(Roles = "admin")]
        public async Task<IActionResult> AdminAdd([FromBody] UpsertTweetDto dto)
        {
            if (string.IsNullOrWhiteSpace(dto.Url) ||
                !Uri.TryCreate(dto.Url.Trim(), UriKind.Absolute, out _))
                return BadRequest(new { error = "Invalid tweet URL." });

            // Validate URL points to x.com or twitter.com
            var clean = dto.Url.Trim();
            if (!clean.Contains("x.com") && !clean.Contains("twitter.com"))
                return BadRequest(new { error = "URL must be from x.com or twitter.com." });

            await using var conn = new NpgsqlConnection(ConnStr);
            var record = await conn.QuerySingleOrDefaultAsync<SocialTweetRecord>(
                @"INSERT INTO social_tweets (url, label, is_active, sort_order)
                  VALUES (@url, @label, @isActive, @sortOrder)
                  ON CONFLICT (url) DO UPDATE
                    SET label = EXCLUDED.label,
                        is_active = EXCLUDED.is_active,
                        sort_order = EXCLUDED.sort_order,
                        updated_at = NOW()
                  RETURNING *",
                new { url = clean, label = dto.Label?.Trim(), isActive = dto.IsActive, sortOrder = dto.SortOrder });

            _cache.Remove(CacheKey);
            return StatusCode(201, record);
        }

        // ── PUT /api/twitter/admin/tweets/{id} — update ──────────────────────
        [HttpPut("admin/tweets/{id:guid}")]
        [Authorize(Roles = "admin")]
        public async Task<IActionResult> AdminUpdate(Guid id, [FromBody] UpsertTweetDto dto)
        {
            await using var conn = new NpgsqlConnection(ConnStr);
            var updated = await conn.QuerySingleOrDefaultAsync<SocialTweetRecord>(
                @"UPDATE social_tweets
                  SET url = @url, label = @label, is_active = @isActive,
                      sort_order = @sortOrder, updated_at = NOW()
                  WHERE id = @id RETURNING *",
                new { id, url = dto.Url?.Trim(), label = dto.Label?.Trim(),
                      isActive = dto.IsActive, sortOrder = dto.SortOrder });

            if (updated is null) return NotFound();
            _cache.Remove(CacheKey);
            return Ok(updated);
        }

        // ── DELETE /api/twitter/admin/tweets/{id} ────────────────────────────
        [HttpDelete("admin/tweets/{id:guid}")]
        [Authorize(Roles = "admin")]
        public async Task<IActionResult> AdminDelete(Guid id)
        {
            await using var conn = new NpgsqlConnection(ConnStr);
            var affected = await conn.ExecuteAsync(
                "DELETE FROM social_tweets WHERE id = @id", new { id });
            if (affected == 0) return NotFound();
            _cache.Remove(CacheKey);
            return Ok(new { message = "Deleted." });
        }

        // ── POST /api/twitter/admin/tweets/{id}/toggle — active toggle ───────
        [HttpPost("admin/tweets/{id:guid}/toggle")]
        [Authorize(Roles = "admin")]
        public async Task<IActionResult> AdminToggle(Guid id)
        {
            await using var conn = new NpgsqlConnection(ConnStr);
            var updated = await conn.QuerySingleOrDefaultAsync<SocialTweetRecord>(
                @"UPDATE social_tweets SET is_active = NOT is_active, updated_at = NOW()
                  WHERE id = @id RETURNING *", new { id });
            if (updated is null) return NotFound();
            _cache.Remove(CacheKey);
            return Ok(updated);
        }
    }

    public record TweetEmbedDto(Guid Id, string Url, string Label, string Html, string AuthorName);
    public record UpsertTweetDto(string Url, string? Label, bool IsActive = true, int SortOrder = 0);

    public class SocialTweetRecord
    {
        public Guid     Id         { get; set; }
        public string   Url        { get; set; } = "";
        public string?  Label      { get; set; }
        public bool     IsActive   { get; set; }
        public int      SortOrder  { get; set; }
        public DateTime CreatedAt  { get; set; }
        public DateTime UpdatedAt  { get; set; }
    }
}
