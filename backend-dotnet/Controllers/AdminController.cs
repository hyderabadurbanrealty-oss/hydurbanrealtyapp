using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Admin endpoints — scrape trigger and scrape run status.
    /// Forwards scrape trigger requests to the Flask service and returns the
    /// resulting scrape_runs record (Req 5.2, 5.5).
    /// Requires admin role.
    /// </summary>
    [ApiController]
    [Route("api/admin")]
    [Authorize]
    public class AdminController : ControllerBase
    {
        private readonly IPythonScraperClient _scraperClient;
        private readonly ILogger<AdminController> _logger;

        public AdminController(IPythonScraperClient scraperClient, ILogger<AdminController> logger)
        {
            _scraperClient = scraperClient;
            _logger        = logger;
        }

        // POST /api/admin/scrape/rera
        [HttpPost("scrape/rera")]
        public async Task<IActionResult> TriggerReraScrape([FromBody] TriggerScrapeRequest? req)
        {
            _logger.LogInformation("Admin triggered RERA scrape");
            try
            {
                var result = await _scraperClient.TriggerBulkScrapeAsync(req?.StartIndex ?? 0);
                return Ok(new { message = "RERA scrape triggered", flaskResponse = result });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to trigger RERA scrape");
                return StatusCode(502, new { error = "scrape_trigger_failed", detail = ex.Message });
            }
        }

        // POST /api/admin/scrape/sro
        [HttpPost("scrape/sro")]
        public async Task<IActionResult> TriggerSroScrape([FromBody] TriggerSroScrapeRequest? req)
        {
            _logger.LogInformation("Admin triggered SRO scrape");
            try
            {
                var result = await _scraperClient.TriggerSroScrapeAsync(
                    req?.Sros ?? Array.Empty<string>(),
                    req?.Years ?? Array.Empty<int>());
                return Ok(new { message = "SRO scrape triggered", flaskResponse = result });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to trigger SRO scrape");
                return StatusCode(502, new { error = "scrape_trigger_failed", detail = ex.Message });
            }
        }

        // POST /api/admin/scrape/rr
        [HttpPost("scrape/rr")]
        public async Task<IActionResult> TriggerRrScrape([FromBody] TriggerRrScrapeRequest? req)
        {
            _logger.LogInformation("Admin triggered RR (unit rates) scrape");
            try
            {
                var result = await _scraperClient.TriggerRrScrapeAsync(req?.Pincodes ?? Array.Empty<string>());
                return Ok(new { message = "RR scrape triggered", flaskResponse = result });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to trigger RR scrape");
                return StatusCode(502, new { error = "scrape_trigger_failed", detail = ex.Message });
            }
        }

        // GET /api/admin/scrape/status
        [HttpGet("scrape/status")]
        public async Task<IActionResult> GetScrapeStatus()
        {
            try
            {
                var status = await _scraperClient.GetScrapingStatusAsync();
                return Ok(status);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to get scrape status");
                return StatusCode(502, new { error = "status_fetch_failed", detail = ex.Message });
            }
        }
    }

    public record TriggerScrapeRequest(int StartIndex = 0);
    public record TriggerSroScrapeRequest(string[] Sros, int[] Years);
    public record TriggerRrScrapeRequest(string[] Pincodes);
}
