using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using Microsoft.Extensions.Options;
using System.Text.Json;
using System.Text;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Service for communicating with Python Flask scraper backend
    /// Follows Single Responsibility - handles HTTP communication with Python service only
    /// Implements IPythonScraperClient for testability and dependency inversion
    /// </summary>
    public class PythonScraperClientService : IPythonScraperClient
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<PythonScraperClientService> _logger;
        private readonly string _pythonApiBaseUrl;

        public PythonScraperClientService(
            IHttpClientFactory httpClientFactory,
            IConfiguration configuration,
            ILogger<PythonScraperClientService> logger)
        {
            _httpClient = httpClientFactory.CreateClient();
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            
            // Get Python API URL from configuration, default to localhost:5000
            _pythonApiBaseUrl = configuration.GetValue<string>("PythonScraperSettings:BaseUrl") 
                ?? "http://localhost:5000";
            
            _httpClient.BaseAddress = new Uri(_pythonApiBaseUrl);
            _httpClient.Timeout = TimeSpan.FromSeconds(300); // 5 minutes for scraping operations
        }

        /// <inheritdoc />
        public async Task<IEnumerable<Dictionary<string, object>>> GetScrapedProjectsAsync()
        {
            try
            {
                _logger.LogInformation("Fetching all scraped projects from Python API");
                
                var response = await _httpClient.GetAsync("/api/projects");
                response.EnsureSuccessStatusCode();
                
                var content = await response.Content.ReadAsStringAsync();
                var projects = JsonSerializer.Deserialize<List<Dictionary<string, object>>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                
                _logger.LogInformation("Successfully fetched {Count} projects from Python API", 
                    projects?.Count ?? 0);
                
                return projects ?? new List<Dictionary<string, object>>();
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "Failed to fetch projects from Python API. Is Flask service running?");
                return new List<Dictionary<string, object>>();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching projects from Python API");
                return new List<Dictionary<string, object>>();
            }
        }

        /// <inheritdoc />
        public async Task<Dictionary<string, object>?> GetScrapedProjectByIdAsync(string projectId)
        {
            try
            {
                _logger.LogInformation("Fetching project {ProjectId} from Python API", projectId);
                
                var response = await _httpClient.GetAsync($"/api/projects/{projectId}");
                
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogWarning("Project {ProjectId} not found in Python API", projectId);
                    return null;
                }
                
                var content = await response.Content.ReadAsStringAsync();
                var project = JsonSerializer.Deserialize<Dictionary<string, object>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                
                _logger.LogInformation("Successfully fetched project {ProjectId} from Python API", projectId);
                
                return project;
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "Failed to fetch project from Python API. Is Flask service running?");
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching project {ProjectId} from Python API", projectId);
                return null;
            }
        }

        /// <inheritdoc />
        public async Task<bool> ScrapeProjectAsync(string projectName)
        {
            try
            {
                _logger.LogInformation("Triggering Python scraper for project: {ProjectName}", projectName);
                
                var payload = new { project_name = projectName };
                var jsonContent = new StringContent(
                    JsonSerializer.Serialize(payload),
                    Encoding.UTF8,
                    "application/json");
                
                var response = await _httpClient.PostAsync("/api/scrape_project", jsonContent);
                response.EnsureSuccessStatusCode();
                
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<Dictionary<string, object>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                
                var status = result?.GetValueOrDefault("status")?.ToString() ?? "error";
                var success = status.Equals("success", StringComparison.OrdinalIgnoreCase);
                
                if (success)
                {
                    _logger.LogInformation("Successfully triggered scraping for project: {ProjectName}", projectName);
                }
                else
                {
                    var message = result?.GetValueOrDefault("message")?.ToString() ?? "Unknown error";
                    _logger.LogWarning("Failed to scrape project {ProjectName}: {Message}", projectName, message);
                }
                
                return success;
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "Failed to trigger scraping. Is Python Flask service running?");
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error triggering scraping for project: {ProjectName}", projectName);
                return false;
            }
        }

        /// <inheritdoc />
        public async Task<bool> FetchAllProjectNamesAsync()
        {
            try
            {
                _logger.LogInformation("Triggering Python scraper to fetch all project names");
                
                var response = await _httpClient.PostAsync("/api/fetch_project_names", null);
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<Dictionary<string, object>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                
                var status = result?.GetValueOrDefault("status")?.ToString() ?? "error";
                var pythonMessage = result?.GetValueOrDefault("message")?.ToString() ?? "Unknown error from Python";
                var success = status.Equals("success", StringComparison.OrdinalIgnoreCase);
                
                if (success)
                {
                    _logger.LogInformation("Successfully triggered project names fetching");
                }
                else
                {
                    _logger.LogWarning("Failed to fetch project names: {Message}", pythonMessage);
                    throw new InvalidOperationException(pythonMessage);
                }
                
                return success;
            }
            catch (InvalidOperationException)
            {
                throw; // re-throw Python error messages as-is
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "Failed to trigger project names fetching. Is Python Flask service running?");
                throw new InvalidOperationException("Cannot reach Python scraper service. Is it running on port 5000?", ex);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error triggering project names fetching");
                return false;
            }
        }

        /// <inheritdoc />
        public async Task<bool> BulkScrapeProjectsAsync(int startIndex = 0)
        {
            try
            {
                _logger.LogInformation("Triggering bulk scraping starting from index {StartIndex}", startIndex);
                
                var payload = new { start_idx = startIndex };
                var jsonContent = new StringContent(
                    JsonSerializer.Serialize(payload),
                    Encoding.UTF8,
                    "application/json");
                
                var response = await _httpClient.PostAsync("/api/bulk_scrape", jsonContent);
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<Dictionary<string, object>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                
                var status = result?.GetValueOrDefault("status")?.ToString() ?? "error";
                var pythonMessage = result?.GetValueOrDefault("message")?.ToString() ?? "Unknown error from Python";
                var success = status.Equals("success", StringComparison.OrdinalIgnoreCase);
                
                if (success)
                {
                    _logger.LogInformation("Successfully triggered bulk scraping from index {StartIndex}", startIndex);
                }
                else
                {
                    _logger.LogWarning("Failed to trigger bulk scraping: {Message}", pythonMessage);
                    throw new InvalidOperationException(pythonMessage);
                }
                
                return success;
            }
            catch (InvalidOperationException)
            {
                throw; // re-throw Python error messages as-is
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "Failed to trigger bulk scraping. Is Python Flask service running?");
                throw new InvalidOperationException("Cannot reach Python scraper service. Is it running on port 5000?", ex);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error triggering bulk scraping from index {StartIndex}", startIndex);
                throw;
            }
        }

        /// <inheritdoc />
        public async Task<bool> IsServiceAvailableAsync()
        {
            try
            {
                _logger.LogDebug("Checking Python Flask service availability");
                
                var response = await _httpClient.GetAsync("/api/projects");
                var available = response.IsSuccessStatusCode;
                
                if (available)
                {
                    _logger.LogDebug("Python Flask service is available");
                }
                else
                {
                    _logger.LogWarning("Python Flask service returned status code: {StatusCode}", 
                        response.StatusCode);
                }
                
                return available;
            }
            catch (HttpRequestException ex)
            {
                _logger.LogWarning(ex, "Python Flask service is not available");
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking Python Flask service availability");
                return false;
            }
        }

        /// <inheritdoc />
        public async Task<Dictionary<string, object>> GetScrapePreferencesAsync()
        {
            try
            {
                var response = await _httpClient.GetAsync("/api/scrape-preferences");
                response.EnsureSuccessStatusCode();
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<Dictionary<string, object>>(content,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                return result ?? new Dictionary<string, object>();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching scrape preferences from Python");
                return new Dictionary<string, object> { ["pincodes"] = new List<string>(), ["localities"] = new List<string>() };
            }
        }

        /// <inheritdoc />
        public async Task<bool> SaveScrapePreferencesAsync(Dictionary<string, object> preferences)
        {
            try
            {
                var jsonContent = new StringContent(
                    JsonSerializer.Serialize(preferences),
                    Encoding.UTF8,
                    "application/json");
                var response = await _httpClient.PostAsync("/api/scrape-preferences", jsonContent);
                response.EnsureSuccessStatusCode();
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error saving scrape preferences to Python");
                return false;
            }
        }

        // ── SRO Transaction Data ─────────────────────────────────────────────

        /// <inheritdoc />
        public async Task<string> GetSroCityAggregateAsync()
            => await ProxyGetAsync("/api/sro/aggregate/city");

        /// <inheritdoc />
        public async Task<string> GetSroLocalityAggregateAsync(string? locality)
        {
            var qs = string.IsNullOrEmpty(locality) ? "" : $"?locality={Uri.EscapeDataString(locality)}";
            return await ProxyGetAsync($"/api/sro/aggregate/locality{qs}");
        }

        /// <inheritdoc />
        public async Task<string> GetSroPriceRankAsync(string? quarter, int top)
        {
            var qs = $"?top={top}";
            if (!string.IsNullOrEmpty(quarter)) qs += $"&quarter={Uri.EscapeDataString(quarter)}";
            return await ProxyGetAsync($"/api/sro/rank/price{qs}");
        }

        /// <inheritdoc />
        public async Task<string> GetSroVolumeRankAsync(string? quarter, int top)
        {
            var qs = $"?top={top}";
            if (!string.IsNullOrEmpty(quarter)) qs += $"&quarter={Uri.EscapeDataString(quarter)}";
            return await ProxyGetAsync($"/api/sro/rank/volume{qs}");
        }

        /// <inheritdoc />
        public async Task<string> GetSroScrapeStatusAsync()
            => await ProxyGetAsync("/api/sro_scrape/status");

        /// <inheritdoc />
        public async Task<string> StartSroScrapeAsync(string jsonPayload)
            => await ProxyPostAsync("/api/sro_scrape", jsonPayload);

        // ── Ready Reckoner (Unit Rate) Scraping ──────────────────────────────

        /// <inheritdoc />
        public async Task<string> GetRrScrapeStatusAsync()
            => await ProxyGetAsync("/api/rr_scrape/status");

        /// <inheritdoc />
        public async Task<string> StartRrScrapeAsync(string jsonPayload)
            => await ProxyPostAsync("/api/rr_scrape", jsonPayload);

        /// <inheritdoc />
        public async Task<string> StopRrScrapeAsync()
            => await ProxyPostAsync("/api/rr_scrape/stop", "{}");

        /// <inheritdoc />
        public async Task<string> GetSroProjectTrendAsync(string name)
            => await ProxyGetAsync($"/api/sro_project_trend?name={Uri.EscapeDataString(name)}");

        /// <inheritdoc />
        public async Task<string> GetSroProjectUnitsAsync(string name)
            => await ProxyGetAsync($"/api/sro_project_units?name={Uri.EscapeDataString(name)}");

        /// <inheritdoc />
        public async Task<string> TriggerBulkScrapeAsync(int startIndex)
            => await ProxyPostAsync("/api/bulk_scrape", $"{{\"start_idx\":{startIndex}}}");

        /// <inheritdoc />
        public async Task<string> TriggerSroScrapeAsync(string[] sros, int[] years)
        {
            var payload = System.Text.Json.JsonSerializer.Serialize(new { sros, years });
            return await ProxyPostAsync("/api/sro_scrape", payload);
        }

        /// <inheritdoc />
        public async Task<string> TriggerRrScrapeAsync(string[] pincodes)
        {
            var payload = System.Text.Json.JsonSerializer.Serialize(new { pincodes });
            return await ProxyPostAsync("/api/rr_scrape", payload);
        }

        /// <inheritdoc />
        public async Task<string> GetScrapingStatusAsync()
            => await ProxyGetAsync("/api/scraping_status");

        // ── internal proxy helpers ────────────────────────────────────────────

        private async Task<string> ProxyGetAsync(string path)
        {
            try
            {
                // Use a short-lived CTS so a slow/offline Python service doesn't hold the .NET
                // request pipeline for the full 300 s HttpClient timeout.
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
                var resp = await _httpClient.GetAsync(path, cts.Token);
                return await resp.Content.ReadAsStringAsync(cts.Token);
            }
            catch (OperationCanceledException)
            {
                _logger.LogWarning("ProxyGet timed out for {Path} — Python service may be offline or slow", path);
                return "{}";
            }
            catch (HttpRequestException ex)
            {
                _logger.LogWarning("ProxyGet connection error for {Path}: {Msg} — Is Flask running?", path, ex.Message);
                return "{}";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "ProxyGet unexpected error for {Path}", path);
                return "{}";
            }
        }

        private async Task<string> ProxyPostAsync(string path, string json)
        {
            try
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(300));
                var content = new StringContent(json, Encoding.UTF8, "application/json");
                var resp    = await _httpClient.PostAsync(path, content, cts.Token);
                return await resp.Content.ReadAsStringAsync(cts.Token);
            }
            catch (OperationCanceledException)
            {
                _logger.LogWarning("ProxyPost timed out for {Path}", path);
                return "{\"status\":\"error\",\"message\":\"Request timed out\"}";
            }
            catch (HttpRequestException ex)
            {
                _logger.LogWarning("ProxyPost connection error for {Path}: {Msg}", path, ex.Message);
                return "{\"status\":\"error\",\"message\":\"Python service unavailable\"}";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "ProxyPost unexpected error for {Path}", path);
                return "{\"status\":\"error\",\"message\":\"Python service unavailable\"}";
            }
        }
    }
}
