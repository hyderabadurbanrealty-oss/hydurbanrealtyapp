using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.DTOs;
using HyderabadUrbanReality.Core.Configuration;
using HyderabadUrbanReality.Models;
using Microsoft.Extensions.Options;
using Microsoft.Extensions.Caching.Memory;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.IdentityModel.Tokens;
using System.Text;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// API Controller for project-related operations
    /// Follows Single Responsibility - handles HTTP concerns only
    /// Follows Dependency Inversion - depends on interfaces
    /// </summary>
    [ApiController]
    [Route("api")]
    public class ProjectController : ControllerBase
    {
        private readonly IProjectService _projectService;
        private readonly IAuthenticationService _authService;
        private readonly IFileService _fileService;
        private readonly IOpenStreetMapService _osmService;
        private readonly IInputSanitizer _inputSanitizer;
        private readonly IPythonScraperClient _pythonScraperClient;
        private readonly AppSettings _appSettings;
        private readonly ILogger<ProjectController> _logger;
        private readonly LeadRepository _leadRepo;
        private readonly IMemoryCache _cache;
        private readonly IEmailService _emailService;

        public ProjectController(
            IProjectService projectService,
            IAuthenticationService authService,
            IFileService fileService,
            IOpenStreetMapService osmService,
            IInputSanitizer inputSanitizer,
            IPythonScraperClient pythonScraperClient,
            IOptions<AppSettings> appSettings,
            ILogger<ProjectController> logger,
            LeadRepository leadRepo,
            IMemoryCache cache,
            IEmailService emailService)
        {
            _projectService = projectService ?? throw new ArgumentNullException(nameof(projectService));
            _authService = authService ?? throw new ArgumentNullException(nameof(authService));
            _fileService = fileService ?? throw new ArgumentNullException(nameof(fileService));
            _osmService = osmService ?? throw new ArgumentNullException(nameof(osmService));
            _inputSanitizer = inputSanitizer ?? throw new ArgumentNullException(nameof(inputSanitizer));
            _pythonScraperClient = pythonScraperClient ?? throw new ArgumentNullException(nameof(pythonScraperClient));
            _appSettings = appSettings?.Value ?? throw new ArgumentNullException(nameof(appSettings));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _leadRepo = leadRepo ?? throw new ArgumentNullException(nameof(leadRepo));
            _cache = cache ?? throw new ArgumentNullException(nameof(cache));
            _emailService = emailService ?? throw new ArgumentNullException(nameof(emailService));
        }

        // ── POST /api/geocode ─────────────────────────────────────────────────
        // Proxies Nominatim server-side (avoids CORS + rate-limit issues from browser).
        // Results cached in IMemoryCache for 30 days — geocodes are stable.
        // Rate-limited to 1 req/sec toward Nominatim via a semaphore.
        private static readonly SemaphoreSlim _geocodeSem = new(1, 1);
        private static DateTime _lastNominatimCall = DateTime.MinValue;
        private static readonly TimeSpan NominatimMinInterval = TimeSpan.FromSeconds(1);
        private static readonly HttpClient _nominatimClient = new()
        {
            Timeout = TimeSpan.FromSeconds(10),
            DefaultRequestHeaders = {
                { "User-Agent", "HyderabadUrbanReality/1.0 (contact: admin@hydurban.in)" },
                { "Accept-Language", "en" }
            }
        };

        [HttpPost("geocode")]
        [AllowAnonymous]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(404)]
        public async Task<IActionResult> Geocode([FromBody] GeocodeRequest req)
        {
            if (req == null) return BadRequest(new { error = "Request body required" });

            // Build a stable cache key from the query parts
            var cacheKey = $"geocode:{req.Locality}|{req.District}|{req.PinCode}".ToLowerInvariant();

            if (_cache.TryGetValue(cacheKey, out object? cached) && cached is not null)
            {
                _logger.LogDebug("Geocode cache HIT — {Key}", cacheKey);
                return Ok(cached);
            }

            // Build progressive query list — most specific to least specific
            var queries = new List<string?>();
            if (!string.IsNullOrWhiteSpace(req.Street) && !string.IsNullOrWhiteSpace(req.Locality))
                queries.Add($"{req.Street}, {req.Locality}, {req.District}, Telangana, India");
            if (!string.IsNullOrWhiteSpace(req.Landmark) && !string.IsNullOrWhiteSpace(req.Locality))
                queries.Add($"{req.Landmark}, {req.Locality}, {req.District}, Telangana, India");
            if (!string.IsNullOrWhiteSpace(req.Locality) && !string.IsNullOrWhiteSpace(req.District))
                queries.Add($"{req.Locality}, {req.District}, Telangana, India");
            if (!string.IsNullOrWhiteSpace(req.Locality))
                queries.Add($"{req.Locality}, Telangana, India");
            if (!string.IsNullOrWhiteSpace(req.District))
                queries.Add($"{req.District}, Telangana, India");
            if (!string.IsNullOrWhiteSpace(req.PinCode))
                queries.Add($"{req.PinCode}, India");

            foreach (var q in queries.Where(x => x != null))
            {
                try
                {
                    // Respect Nominatim 1-req/sec policy
                    await _geocodeSem.WaitAsync();
                    try
                    {
                        var elapsed = DateTime.UtcNow - _lastNominatimCall;
                        if (elapsed < NominatimMinInterval)
                            await Task.Delay(NominatimMinInterval - elapsed);
                        _lastNominatimCall = DateTime.UtcNow;
                    }
                    finally { _geocodeSem.Release(); }

                    var url  = $"https://nominatim.openstreetmap.org/search" +
                               $"?q={Uri.EscapeDataString(q!)}&format=json&limit=1&countrycodes=in";
                    var resp = await _nominatimClient.GetAsync(url);

                    if (!resp.IsSuccessStatusCode) continue;

                    var json  = await resp.Content.ReadAsStringAsync();
                    using var doc = System.Text.Json.JsonDocument.Parse(json);
                    var arr = doc.RootElement;

                    if (arr.ValueKind == System.Text.Json.JsonValueKind.Array && arr.GetArrayLength() > 0)
                    {
                        var first = arr[0];
                        var result = new
                        {
                            lat = double.Parse(first.GetProperty("lat").GetString()!,
                                              System.Globalization.CultureInfo.InvariantCulture),
                            lng = double.Parse(first.GetProperty("lon").GetString()!,
                                              System.Globalization.CultureInfo.InvariantCulture)
                        };

                        // Cache for 30 days — Hyderabad locality names don't move
                        var opts = new MemoryCacheEntryOptions()
                            .SetAbsoluteExpiration(TimeSpan.FromDays(30));
                        _cache.Set(cacheKey, (object)result, opts);

                        _logger.LogDebug("Geocoded '{Query}' → {Lat},{Lng}", q, result.lat, result.lng);
                        return Ok(result);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Nominatim query failed: {Query}", q);
                }
            }

            return NotFound(new { error = "Could not geocode the given address" });
        }

        /// Returns HTTP 304 if the client's ETag matches, avoiding payload transfer.
        /// </summary>
        [HttpGet("projects")]
        [ProducesResponseType(typeof(IEnumerable<Dictionary<string, object>>), 200)]
        [ProducesResponseType(304)]
        public async Task<IActionResult> GetProjects()
        {
            try
            {
                var projects = await _projectService.GetAllProjectsAsync();
                var list = projects.ToList();

                // Build a lightweight ETag from count + first project id so clients
                // can skip downloading the payload when nothing has changed.
                var etag = $"\"{list.Count}-{list.FirstOrDefault()?.GetValueOrDefault("id")}\"";

                // 304 Not Modified — client already has the current version
                if (Request.Headers.TryGetValue("If-None-Match", out var inm) && inm == etag)
                    return StatusCode(304);

                Response.Headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60";
                Response.Headers["ETag"]          = etag;
                Response.Headers["Vary"]          = "Accept-Encoding";

                _logger.LogInformation("GET /api/projects → {Count} projects", list.Count);
                return Ok(list);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching projects");
                return StatusCode(500, new { error = "An error occurred while fetching projects" });
            }
        }

        /// <summary>
        /// Gets a specific project by ID — served from memory cache after first hit.
        /// </summary>
        [HttpGet("projects/{id}")]
        [ProducesResponseType(typeof(Dictionary<string, object>), 200)]
        [ProducesResponseType(304)]
        [ProducesResponseType(404)]
        public async Task<IActionResult> GetProject(string id)
        {
            try
            {
                var project = await _projectService.GetProjectByIdAsync(id);

                if (project == null)
                    return NotFound(new { error = $"Project '{id}' not found" });

                var etag = $"\"{id}-{project.GetValueOrDefault("scraped_at") ?? project.GetValueOrDefault("Approved Date")}\"";

                if (Request.Headers.TryGetValue("If-None-Match", out var inm) && inm == etag)
                    return StatusCode(304);

                Response.Headers["Cache-Control"] = "public, max-age=600, stale-while-revalidate=120";
                Response.Headers["ETag"]          = etag;

                _logger.LogInformation("GET /api/projects/{Id}", id);
                return Ok(project);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching project: {Id}", id);
                return StatusCode(500, new { error = "An error occurred while fetching the project" });
            }
        }

        /// <summary>
        /// Authenticates user and returns JWT token
        /// </summary>
        [HttpPost("login")]
        [ProducesResponseType(typeof(LoginResponseDto), 200)]
        [ProducesResponseType(typeof(LoginResponseDto), 401)]
        public async Task<IActionResult> Login([FromBody] LoginRequestDto request)
        {
            try
            {
                _logger.LogInformation("POST /api/login - Attempt for user: {Username}", request.Username);
                
                var isAuthenticated = await _authService.AuthenticateAsync(request.Username, request.Password);
                
                if (isAuthenticated)
                {
                    // Generate JWT token
                    var tokenHandler = new JwtSecurityTokenHandler();
                    var key = Encoding.ASCII.GetBytes(_appSettings.JwtSecret);
                    var tokenDescriptor = new SecurityTokenDescriptor
                    {
                        Subject = new ClaimsIdentity(new[]
                        {
                            new Claim(ClaimTypes.Name, request.Username),
                            new Claim(ClaimTypes.Role, "Admin")
                        }),
                        Expires = DateTime.UtcNow.AddHours(2),
                        SigningCredentials = new SigningCredentials(
                            new SymmetricSecurityKey(key), 
                            SecurityAlgorithms.HmacSha256Signature)
                    };
                    var token = tokenHandler.CreateToken(tokenDescriptor);
                    var tokenString = tokenHandler.WriteToken(token);

                    // Also set session for backward compatibility
                    HttpContext.Session.SetString("is_admin", "true");
                    
                    return Ok(new LoginResponseDto 
                    { 
                        Status = "success",
                        Token = tokenString
                    });
                }

                _logger.LogWarning("Failed login attempt for user: {Username}", request.Username);
                return Unauthorized(new LoginResponseDto 
                { 
                    Status = "error", 
                    Message = "Invalid credentials" 
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during login");
                return StatusCode(500, new LoginResponseDto
                {
                    Status = "error",
                    Message = "An error occurred during authentication"
                });
            }
        }

        /// <summary>
        /// Logs out current user
        /// </summary>
        [HttpPost("logout")]
        public IActionResult Logout()
        {
            _logger.LogInformation("POST /api/logout");
            HttpContext.Session.Remove("is_admin");
            return Ok(new { status = "success" });
        }

        /// <summary>
        /// Fetches project names - Redirects to Python scraper
        /// </summary>
        [HttpPost("fetch_project_names")]
        public async Task<IActionResult> FetchProjectNames([FromBody] Dictionary<string, string>? request)
        {
            try
            {
                _logger.LogInformation("POST /api/fetch_project_names - Redirecting to Python scraper");
                
                var success = await _pythonScraperClient.FetchAllProjectNamesAsync();
                
                if (success)
                {
                    return Ok(new { status = "success", message = "Project names fetching triggered" });
                }
                
                return StatusCode(500, new { status = "error", message = "Failed to trigger project names fetching" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching project names");
                return StatusCode(500, new { status = "error", message = ex.Message });
            }
        }

        /// <summary>
        /// Scrapes a specific project - Redirects to Python scraper
        /// </summary>
        [HttpPost("scrape_project")]
        public async Task<IActionResult> ScrapeProject([FromBody] Dictionary<string, string> request)
        {
            try
            {
                var projectName = request.GetValueOrDefault("project_name");
                
                if (string.IsNullOrWhiteSpace(projectName))
                {
                    return BadRequest(new { status = "error", message = "project_name is required" });
                }
                
                _logger.LogInformation("POST /api/scrape_project - Project: {ProjectName} - Redirecting to Python", projectName);
                
                var success = await _pythonScraperClient.ScrapeProjectAsync(projectName);
                
                if (success)
                {
                    return Ok(new { status = "success", message = $"Scraping triggered for {projectName}" });
                }
                
                return StatusCode(500, new { status = "error", message = "Failed to trigger scraping" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error triggering scrape");
                return StatusCode(500, new { status = "error", message = ex.Message });
            }
        }

        /// <summary>
        /// Triggers bulk scraping - Redirects to Python scraper
        /// </summary>
        [HttpPost("bulk_scrape")]
        public async Task<IActionResult> BulkScrape([FromBody] Dictionary<string, int>? request)
        {
            try
            {
                var startIndex = request?.GetValueOrDefault("start_idx") ?? 0;
                
                _logger.LogInformation("POST /api/bulk_scrape - Start index: {StartIndex} - Redirecting to Python", startIndex);
                
                var success = await _pythonScraperClient.BulkScrapeProjectsAsync(startIndex);
                
                if (success)
                {
                    return Ok(new { status = "success", message = $"Bulk scraping triggered from index {startIndex}" });
                }
                
                return StatusCode(500, new { status = "error", message = "Failed to trigger bulk scraping" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error triggering bulk scrape");
                return StatusCode(500, new { status = "error", message = ex.Message });
            }
        }

        /// <summary>
        /// Gets saved pincode/locality scrape preferences - Admin only
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpGet("scrape-preferences")]
        public async Task<IActionResult> GetScrapePreferences()
        {
            try
            {
                var prefs = await _pythonScraperClient.GetScrapePreferencesAsync();
                return Ok(prefs);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting scrape preferences");
                return StatusCode(500, new { status = "error", message = ex.Message });
            }
        }

        /// <summary>
        /// Saves pincode/locality scrape preferences - Admin only
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpPost("scrape-preferences")]
        public async Task<IActionResult> SaveScrapePreferences([FromBody] Dictionary<string, object> preferences)
        {
            try
            {
                var success = await _pythonScraperClient.SaveScrapePreferencesAsync(preferences);
                if (success)
                    return Ok(new { status = "success", message = "Preferences saved." });
                return StatusCode(500, new { status = "error", message = "Failed to save preferences" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error saving scrape preferences");
                return StatusCode(500, new { status = "error", message = ex.Message });
            }
        }

        /// <summary>
        /// Uploads a file (brochure, image, etc.) - Admin only
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpPost("upload")]
        [ProducesResponseType(typeof(FileUploadResponseDto), 200)]
        [ProducesResponseType(400)]
        public async Task<IActionResult> UploadFile(IFormFile file)
        {
            try
            {
                if (file == null || file.Length == 0)
                {
                    return BadRequest(new ApiResponseDto<object>
                    {
                        Success = false,
                        Message = "No file uploaded"
                    });
                }

                _logger.LogInformation("POST /api/upload - File: {FileName}, Size: {Size}", 
                    file.FileName, file.Length);

                // Validate file
                if (!_fileService.ValidateFile(file.FileName, file.Length))
                {
                    return BadRequest(new ApiResponseDto<object>
                    {
                        Success = false,
                        Message = "Invalid file type or size exceeds limit"
                    });
                }

                // Upload file
                using var stream = file.OpenReadStream();
                var savedFileName = await _fileService.UploadFileAsync(stream, file.FileName);

                return Ok(new FileUploadResponseDto
                {
                    Status = "success",
                    FileName = savedFileName,
                    FileSize = file.Length
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error uploading file");
                return StatusCode(500, new ApiResponseDto<object>
                {
                    Success = false,
                    Message = "Internal server error",
                    Errors = new List<string> { ex.Message }
                });
            }
        }

        /// <summary>
        /// Gets neighborhood data for a specific project using OpenStreetMap
        /// Uses smart geocoding with multiple fallback strategies for accuracy
        /// </summary>
        [HttpGet("projects/{id}/neighborhood-data")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetProjectNeighborhoodData(string id)
        {
            try
            {
                _logger.LogInformation("GET /api/projects/{Id}/neighborhood-data", id);
                
                // Get project to extract location info
                var project = await _projectService.GetProjectByIdAsync(id);
                
                if (project == null)
                {
                    return NotFound(new { error = $"Project '{id}' not found" });
                }
                
                // Extract location data from project
                var locality = GetValueFromProject(project, "Locality");
                var pincode = GetValueFromProject(project, "Pin Code");
                var district = GetValueFromProject(project, "District");
                var projectName = GetValueFromProject(project, "Project Name");
                
                _logger.LogInformation("Fetching neighborhood data for {ProjectName} - Locality: {Locality}, PIN: {Pincode}, District: {District}",
                    projectName, locality, pincode, district);
                
                // Try to geocode using smart multi-strategy approach
                var coordinates = await _osmService.SmartGeocodeAsync(
                    locality: locality ?? "",
                    district: district ?? "",
                    pinCode: pincode ?? "");
                
                if (coordinates == null)
                {
                    _logger.LogWarning("Could not geocode location for project {ProjectName}", projectName);
                    return Ok(new
                    {
                        error = "Could not determine location",
                        schools = new List<object>(),
                        hospitals = new List<object>(),
                        transport = new List<object>(),
                        shopping = new List<object>(),
                        entertainment = new List<object>(),
                        parks = new List<object>()
                    });
                }
                
                _logger.LogInformation("Successfully geocoded to coordinates: {Lat}, {Lng}", 
                    coordinates.Value.latitude, coordinates.Value.longitude);
                
                // Fetch neighborhood data using the geocoded coordinates
                var osmData = await _osmService.GetNeighborhoodDataAsync(
                    coordinates.Value.latitude,
                    coordinates.Value.longitude,
                    district ?? "Hyderabad"
                );
                
                // Transform OSM data to frontend format
                var neighborhoodData = TransformNeighborhoodData(osmData);
                
                _logger.LogInformation("Successfully fetched neighborhood data for {ProjectName}", projectName);
                
                return Ok(neighborhoodData);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching neighborhood data for project: {Id}", id);
                return StatusCode(500, new { error = ex.Message });
            }
        }
        
        /// <summary>
        /// Helper method to safely extract values from project dictionary
        /// </summary>
        private string? GetValueFromProject(Dictionary<string, object> project, string key)
        {
            if (project.TryGetValue(key, out var value))
            {
                return value?.ToString();
            }
            return null;
        }
        
        /// <summary>
        /// Transforms OSM data structure to frontend-compatible format
        /// Combines OSM categories into frontend categories: shopping & entertainment
        /// </summary>
        private Dictionary<string, object> TransformNeighborhoodData(Dictionary<string, object> osmData)
        {
            var result = new Dictionary<string, object>
            {
                ["latitude"] = osmData.GetValueOrDefault("latitude", 0),
                ["longitude"] = osmData.GetValueOrDefault("longitude", 0),
                ["district"] = osmData.GetValueOrDefault("district", ""),
                ["schools"] = new List<object>(),
                ["hospitals"] = new List<object>(),
                ["transport"] = new List<object>(),
                ["shopping"] = new List<object>(), // Combines supermarkets, banks, restaurants
                ["entertainment"] = new List<object>(), // Restaurants, cafes, entertainment venues
                ["parks"] = new List<object>()
            };
            
            // Extract points_of_interest
            if (osmData.TryGetValue("points_of_interest", out var poisObj))
            {
                Dictionary<string, List<Dictionary<string, object>>>? pois = null;
                
                // Handle different possible types
                if (poisObj is Dictionary<string, List<Dictionary<string, object>>> typedPois)
                {
                    pois = typedPois;
                }
                else if (poisObj is IDictionary<string, object> dictPois)
                {
                    // Convert from generic dictionary
                    pois = new Dictionary<string, List<Dictionary<string, object>>>();
                    foreach (var kvp in dictPois)
                    {
                        if (kvp.Value is List<Dictionary<string, object>> list)
                        {
                            pois[kvp.Key] = list;
                        }
                        else if (kvp.Value is IEnumerable<object> enumerable)
                        {
                            pois[kvp.Key] = enumerable
                                .OfType<Dictionary<string, object>>()
                                .ToList();
                        }
                    }
                }
                
                if (pois != null)
                {
                    // Map OSM categories to frontend keys
                    // Note: Some categories map to multiple frontend keys
                    foreach (var kvp in pois)
                    {
                        var osmCategory = kvp.Key;
                        var places = kvp.Value;
                        
                        switch (osmCategory.ToLowerInvariant())
                        {
                            case "school":
                                AppendToCategory(result, "schools", places);
                                break;
                                
                            case "hospital":
                            case "clinic":
                                AppendToCategory(result, "hospitals", places);
                                break;
                                
                            case "restaurant":
                            case "cafe":
                            case "fast_food":
                                // Add restaurants to BOTH shopping and entertainment
                                AppendToCategory(result, "shopping", places);
                                AppendToCategory(result, "entertainment", places);
                                break;
                                
                            case "supermarket":
                            case "bank":
                            case "atm":
                            case "shop":
                                AppendToCategory(result, "shopping", places);
                                break;
                                
                            case "park":
                            case "garden":
                                AppendToCategory(result, "parks", places);
                                break;
                                
                            case "station":
                            case "public_transport":
                            case "bus_station":
                            case "metro_station":
                                AppendToCategory(result, "transport", places);
                                break;
                                
                            case "cinema":
                            case "theatre":
                            case "museum":
                            case "entertainment":
                                AppendToCategory(result, "entertainment", places);
                                break;
                        }
                    }
                }
            }
            
            // Limit each category to top 4 closest places
            foreach (var key in result.Keys.ToList())
            {
                if (result[key] is List<object> list && list.Count > 0)
                {
                    // Sort by distance if available, then take top 4
                    var sorted = list
                        .Cast<Dictionary<string, object>>()
                        .OrderBy(p => p.ContainsKey("distance") ? Convert.ToDouble(p["distance"]) : double.MaxValue)
                        .Take(4)
                        .Cast<object>()
                        .ToList();
                    result[key] = sorted;
                }
            }
            
            return result;
        }
        
        /// <summary>
        /// Helper method to append places to a category
        /// </summary>
        private void AppendToCategory(Dictionary<string, object> result, string category, List<Dictionary<string, object>> places)
        {
            if (!result.ContainsKey(category))
            {
                result[category] = new List<object>();
            }
            
            var list = result[category] as List<object> ?? new List<object>();
            list.AddRange(places.Cast<object>());
            result[category] = list;
        }

        /// <summary>
        /// Submit lead information from property detail page
        /// </summary>
        [HttpPost("submit_lead")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 400)]
        public async Task<IActionResult> SubmitLead([FromBody] Lead leadData)
        {
            try
            {
                // Sanitize all user inputs to prevent XSS
                leadData.Name = _inputSanitizer.Sanitize(leadData.Name);
                leadData.Email = _inputSanitizer.Sanitize(leadData.Email);
                leadData.Mobile = _inputSanitizer.Sanitize(leadData.Mobile);
                leadData.AreaOfInterest = _inputSanitizer.Sanitize(leadData.AreaOfInterest);
                if (!string.IsNullOrEmpty(leadData.ProjectName))
                    leadData.ProjectName = _inputSanitizer.Sanitize(leadData.ProjectName);

                // Log without exposing full PII
                _logger.LogInformation("POST /api/submit_lead - Receiving lead from area: {Area}", 
                    leadData.AreaOfInterest?.Substring(0, Math.Min(10, leadData.AreaOfInterest.Length)));

                // Validate required fields
                if (string.IsNullOrWhiteSpace(leadData.Name) || 
                    string.IsNullOrWhiteSpace(leadData.Email) || 
                    string.IsNullOrWhiteSpace(leadData.Mobile) || 
                    string.IsNullOrWhiteSpace(leadData.AreaOfInterest))
                {
                    return BadRequest(new { status = "error", message = "All fields are required" });
                }

                // Validate email format
                var emailRegex = new Regex(@"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$");
                if (!emailRegex.IsMatch(leadData.Email))
                {
                    return BadRequest(new { status = "error", message = "Invalid email format" });
                }

                // Validate mobile (10 digits)
                var mobileRegex =new Regex(@"^\d{10}$");
                if (!mobileRegex.IsMatch(leadData.Mobile))
                {
                    return BadRequest(new { status = "error", message = "Mobile number must be 10 digits" });
                }

                // Set timestamp if not provided
                if (leadData.Timestamp == default)
                {
                    leadData.Timestamp = DateTime.UtcNow;
                }

                // Save to PostgreSQL leads table
                var insertedId = await _leadRepo.InsertAsync(leadData);

                _logger.LogInformation("Lead saved to DB (id={Id}): {Name} - {Email} - Project: {ProjectName}",
                    insertedId, leadData.Name, leadData.Email, leadData.ProjectName ?? "Unknown");

                // Send admin notification + enquirer acknowledgement (non-blocking)
                _ = Task.Run(async () =>
                {
                    try
                    {
                        await _emailService.SendLeadNotificationAsync(
                            leadData.Name,
                            leadData.Email,
                            leadData.Mobile,
                            leadData.ProjectName,
                            leadData.AreaOfInterest,
                            leadData.Source ?? "property_detail_page"
                        );
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Lead email notification failed for lead id={Id}", insertedId);
                    }
                });

                return Ok(new { status = "success", message = "Lead information saved successfully", id = insertedId });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error saving lead");
                return StatusCode(500, new { status = "error", message = "An error occurred while saving your information" });
            }
        }

        /// <summary>
        /// Check if a device/user has already unlocked content
        /// </summary>
        [HttpGet("check_unlock")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> CheckUnlock([FromQuery] string fingerprint)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(fingerprint))
                {
                    return Ok(new { unlocked = false });
                }

                var projectRoot = Directory.GetCurrentDirectory();
                var leadsFilePath = Path.Combine(projectRoot, "leads.json");
                
                if (!System.IO.File.Exists(leadsFilePath))
                {
                    return Ok(new { unlocked = false });
                }

                var jsonContent = await System.IO.File.ReadAllTextAsync(leadsFilePath);
                var leads = JsonSerializer.Deserialize<List<Lead>>(jsonContent) ?? new List<Lead>();

                // Check if this fingerprint exists in any lead
                var hasUnlocked = leads.Any(l => l.DeviceFingerprint == fingerprint);

                return Ok(new { unlocked = hasUnlocked });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking unlock status");
                return Ok(new { unlocked = false });
            }
        }

        /// <summary>
        /// Get all captured leads (admin only)
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpGet("leads")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 401)]
        public async Task<IActionResult> GetLeads()
        {
            try
            {
                var leads = await _leadRepo.GetAllAsync();
                var leadList = leads.ToList();
                return Ok(new { status = "success", leads = leadList, count = leadList.Count });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching leads");
                return StatusCode(500, new { status = "error", message = "An error occurred while retrieving leads" });
            }
        }

        /// <summary>
        /// Delete a project by ID (admin only)
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpDelete("projects/{id}")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 404)]
        [ProducesResponseType(typeof(object), 401)]
        public async Task<IActionResult> DeleteProject(string id)
        {
            try
            {
                _logger.LogInformation("DELETE /api/projects/{Id}", id);
                
                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                {
                    return StatusCode(500, new { status = "error", message = "Could not determine parent directory" });
                }

                var backendPath = Path.Combine(parentDir, "backend");
                var scrapedProjectsPath = Path.Combine(backendPath, "scraped_projects");
                var projectPath = Path.Combine(scrapedProjectsPath, id);

                if (!Directory.Exists(projectPath))
                {
                    return NotFound(new { status = "error", message = $"Project '{id}' not found" });
                }

                // Delete the project directory and all its contents
                Directory.Delete(projectPath, recursive: true);

                _logger.LogInformation("Successfully deleted project: {Id}", id);
                return Ok(new { status = "success", message = $"Project '{id}' deleted successfully" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting project {Id}", id);
                return StatusCode(500, new { status = "error", message = "An error occurred while deleting the project" });
            }
        }

        /// <summary>
        /// Save pricing for a project (admin only).
        /// Persists to pricing.json (current snapshot) and appends a timestamped
        /// entry to price_history.json so the frontend can render a trend chart.
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpPut("projects/{id}/pricing")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 404)]
        [ProducesResponseType(typeof(object), 401)]
        public async Task<IActionResult> SavePricing(string id, [FromBody] JsonElement pricingData)
        {
            try
            {
                _logger.LogInformation("PUT /api/projects/{Id}/pricing", id);

                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                    return StatusCode(500, new { status = "error", message = "Could not determine parent directory" });

                var projectPath = Path.Combine(parentDir, "backend", "scraped_projects", id);
                if (!Directory.Exists(projectPath))
                    return NotFound(new { status = "error", message = $"Project '{id}' not found" });

                var options = new JsonSerializerOptions { WriteIndented = true };

                // 1. Overwrite pricing.json (always reflects latest snapshot)
                var pricingPath = Path.Combine(projectPath, "pricing.json");
                await System.IO.File.WriteAllTextAsync(pricingPath, JsonSerializer.Serialize(pricingData, options));

                // 2. Append to price_history.json (append-only log)
                var historyPath = Path.Combine(projectPath, "price_history.json");
                var history = new List<object>();

                if (System.IO.File.Exists(historyPath))
                {
                    var existingJson = await System.IO.File.ReadAllTextAsync(historyPath);
                    history = JsonSerializer.Deserialize<List<object>>(existingJson) ?? new List<object>();
                }

                // Build the snapshot entry
                var snapshot = new Dictionary<string, object>
                {
                    ["timestamp"] = DateTime.UtcNow.ToString("o"),
                    ["date"] = DateTime.UtcNow.ToString("yyyy-MM-dd"),
                    ["data"] = pricingData
                };

                history.Add(snapshot);
                await System.IO.File.WriteAllTextAsync(historyPath, JsonSerializer.Serialize(history, options));

                _logger.LogInformation("Saved pricing snapshot for project {Id}", id);
                return Ok(new { status = "success", message = "Pricing saved", snapshotCount = history.Count });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error saving pricing for project {Id}", id);
                return StatusCode(500, new { status = "error", message = "An error occurred while saving pricing" });
            }
        }

        /// <summary>
        /// Get full price history for a project (for trend chart)
        /// </summary>
        [HttpGet("projects/{id}/price-history")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetPriceHistory(string id)
        {
            try
            {
                _logger.LogInformation("GET /api/projects/{Id}/price-history", id);

                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                    return StatusCode(500, new { status = "error", message = "Could not determine parent directory" });

                var historyPath = Path.Combine(parentDir, "backend", "scraped_projects", id, "price_history.json");

                if (!System.IO.File.Exists(historyPath))
                    return Ok(new List<object>());

                var json = await System.IO.File.ReadAllTextAsync(historyPath);
                var history = JsonSerializer.Deserialize<List<object>>(json) ?? new List<object>();
                return Ok(history);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error reading price history for project {Id}", id);
                return StatusCode(500, new { status = "error", message = "An error occurred while reading price history" });
            }
        }

        /// <summary>
        /// Returns the floor-plan manifest for a project.
        /// The manifest is produced by download_project_docs.py and lives at
        /// scraped_projects/{id}/floor-plans/manifest.json
        /// </summary>
        [HttpGet("projects/{id}/floor-plans")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetFloorPlans(string id)
        {
            try
            {
                // Sanitize id: strip any path separators to prevent traversal
                var sanitizedId = Path.GetFileName(id.Replace('/', '_').Replace('\\', '_'));
                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                    return StatusCode(500, new { error = "Could not determine parent directory" });

                var manifestPath = Path.Combine(parentDir, "backend", "scraped_projects", sanitizedId, "floor-plans", "manifest.json");
                if (!System.IO.File.Exists(manifestPath))
                    return Ok(new List<object>());

                var json = await System.IO.File.ReadAllTextAsync(manifestPath);
                using var doc = JsonDocument.Parse(json);
                var entries = new List<object>();
                foreach (var prop in doc.RootElement.EnumerateObject())
                {
                    var pages = prop.Value.TryGetProperty("pages", out var pagesEl)
                        ? pagesEl.EnumerateArray().Select(p => p.GetString()).ToList()
                        : new List<string?>();
                    entries.Add(new
                    {
                        key      = prop.Name,
                        docName  = prop.Value.TryGetProperty("doc_name",  out var dn) ? dn.GetString() : "",
                        label    = prop.Value.TryGetProperty("label",     out var lb) ? lb.GetString() : "",
                        upid     = prop.Value.TryGetProperty("upid",      out var up) ? up.GetString() : "",
                        pages    = pages.Select(p => $"/api/projects/{sanitizedId}/floor-plans/{p}").ToList()
                    });
                }
                return Ok(entries);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error reading floor-plan manifest for {Id}", id);
                return StatusCode(500, new { error = "Error reading floor plans" });
            }
        }

        /// <summary>
        /// Serves a single floor-plan image file.
        /// </summary>
        [HttpGet("projects/{id}/floor-plans/{filename}")]
        public IActionResult GetFloorPlanImage(string id, string filename)
        {
            try
            {
                // Sanitize both path components to prevent path traversal
                var sanitizedId = Path.GetFileName(id.Replace('/', '_').Replace('\\', '_'));
                var sanitizedFile = Path.GetFileName(filename); // strips any path components
                if (string.IsNullOrWhiteSpace(sanitizedFile) || sanitizedFile.StartsWith('.'))
                    return BadRequest(new { error = "Invalid filename" });

                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                    return StatusCode(500, new { error = "Could not determine parent directory" });

                var imagePath = Path.Combine(parentDir, "backend", "scraped_projects", sanitizedId, "floor-plans", sanitizedFile);
                // Verify the resolved path is inside the expected directory (prevents traversal)
                var expectedBase = Path.GetFullPath(Path.Combine(parentDir, "backend", "scraped_projects", sanitizedId, "floor-plans"));
                var resolvedPath = Path.GetFullPath(imagePath);
                if (!resolvedPath.StartsWith(expectedBase, StringComparison.OrdinalIgnoreCase))
                    return BadRequest(new { error = "Invalid path" });

                if (!System.IO.File.Exists(resolvedPath))
                    return NotFound();

                var ext = Path.GetExtension(sanitizedFile).ToLowerInvariant();
                var contentType = ext switch
                {
                    ".png"  => "image/png",
                    ".jpg" or ".jpeg" => "image/jpeg",
                    _       => "application/octet-stream"
                };
                return PhysicalFile(resolvedPath, contentType);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error serving floor-plan image {Id}/{File}", id, filename);
                return StatusCode(500, new { error = "Error serving image" });
            }
        }

        /// <summary>
        /// Deletes a single scraped floor-plan image and removes it from manifest.json.
        /// </summary>
        [HttpDelete("projects/{id}/floor-plans/{filename}")]
        [Authorize]
        public async Task<IActionResult> DeleteScrapedFloorPlan(string id, string filename)
        {
            try
            {
                var sanitizedId   = Path.GetFileName(id.Replace('/', '_').Replace('\\', '_'));
                var sanitizedFile = Path.GetFileName(filename);
                if (string.IsNullOrWhiteSpace(sanitizedFile) || sanitizedFile.StartsWith('.'))
                    return BadRequest(new { error = "Invalid filename" });

                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir   = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                    return StatusCode(500, new { error = "Server path error" });

                var fpDir         = Path.GetFullPath(Path.Combine(parentDir, "backend", "scraped_projects", sanitizedId, "floor-plans"));
                var resolvedPath  = Path.GetFullPath(Path.Combine(fpDir, sanitizedFile));
                if (!resolvedPath.StartsWith(fpDir, StringComparison.OrdinalIgnoreCase))
                    return BadRequest(new { error = "Invalid path" });

                if (System.IO.File.Exists(resolvedPath))
                    System.IO.File.Delete(resolvedPath);

                // Remove from manifest.json
                var manifestPath = Path.Combine(fpDir, "manifest.json");
                if (System.IO.File.Exists(manifestPath))
                {
                    var manifestJson = await System.IO.File.ReadAllTextAsync(manifestPath);
                    using var doc    = JsonDocument.Parse(manifestJson);
                    var updated      = new Dictionary<string, object>();
                    foreach (var entry in doc.RootElement.EnumerateObject())
                    {
                        if (!entry.Value.TryGetProperty("pages", out var pagesEl)) { updated[entry.Name] = entry.Value; continue; }
                        var remainingPages = pagesEl.EnumerateArray()
                            .Select(p => p.GetString())
                            .Where(p => p != sanitizedFile)
                            .ToList();
                        if (remainingPages.Count > 0)
                        {
                            updated[entry.Name] = new
                            {
                                doc_name = entry.Value.TryGetProperty("doc_name", out var dn) ? dn.GetString() : "",
                                label    = entry.Value.TryGetProperty("label",    out var lb) ? lb.GetString() : "",
                                upid     = entry.Value.TryGetProperty("upid",     out var up) ? up.GetString() : "",
                                pages    = remainingPages
                            };
                        }
                        // If no pages remain, drop the entry entirely
                    }
                    await System.IO.File.WriteAllTextAsync(manifestPath,
                        System.Text.Json.JsonSerializer.Serialize(updated,
                            new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
                }

                return NoContent();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting scraped floor-plan {Id}/{File}", id, filename);
                return StatusCode(500, new { error = "Error deleting file" });
            }
        }

        /// <summary>
        /// Create a new project manually (admin only)
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpPost("projects")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 400)]
        [ProducesResponseType(typeof(object), 401)]
        public async Task<IActionResult> CreateProject([FromBody] Dictionary<string, object> projectData)
        {
            try
            {
                _logger.LogInformation("POST /api/projects - Creating new project");
                
                if (projectData == null || !projectData.ContainsKey("Project Name"))
                {
                    return BadRequest(new { status = "error", message = "Project Name is required" });
                }

                var projectName = projectData["Project Name"].ToString();
                if (string.IsNullOrWhiteSpace(projectName))
                {
                    return BadRequest(new { status = "error", message = "Project Name cannot be empty" });
                }

                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir = Directory.GetParent(projectRoot)?.FullName;
                if (parentDir == null)
                {
                    return StatusCode(500, new { status = "error", message = "Could not determine parent directory" });
                }

                var backendPath = Path.Combine(parentDir, "backend");
                var scrapedProjectsPath = Path.Combine(backendPath, "scraped_projects");
                
                // Create project folder with sanitized name
                var sanitizedName = string.Join("_", projectName!.Split(Path.GetInvalidFileNameChars()));
                var projectPath = Path.Combine(scrapedProjectsPath, sanitizedName);

                if (Directory.Exists(projectPath))
                {
                    return BadRequest(new { status = "error", message = $"Project '{projectName}' already exists" });
                }

                Directory.CreateDirectory(projectPath);

                // Add default fields
                projectData["id"] = sanitizedName;
                if (!projectData.ContainsKey("Project Status")) projectData["Project Status"] = "New";
                if (!projectData.ContainsKey("Project Type")) projectData["Project Type"] = "Residential";

                // Save project data to view_page_data.json
                var jsonPath = Path.Combine(projectPath, "view_page_data.json");
                var options = new JsonSerializerOptions { WriteIndented = true };
                var jsonContent = JsonSerializer.Serialize(projectData, options);
                await System.IO.File.WriteAllTextAsync(jsonPath, jsonContent);

                _logger.LogInformation("Successfully created project: {ProjectName}", projectName);
                return Ok(new { status = "success", message = $"Project '{projectName}' created successfully", projectId = sanitizedName });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating project");
                return StatusCode(500, new { status = "error", message = "An error occurred while creating the project" });
            }
        }

        /// <summary>
        /// Delete a lead by ID (admin only)
        /// </summary>
        [Authorize(Roles = "Admin")]
        [HttpDelete("leads/{index}")]
        [ProducesResponseType(typeof(object), 200)]
        [ProducesResponseType(typeof(object), 404)]
        [ProducesResponseType(typeof(object), 401)]
        public async Task<IActionResult> DeleteLead(int index)
        {
            try
            {
                _logger.LogInformation("DELETE /api/leads/{Id}", index);
                var deleted = await _leadRepo.DeleteAsync(index);
                if (!deleted)
                    return NotFound(new { status = "error", message = $"Lead {index} not found" });
                return Ok(new { status = "success", message = "Lead deleted successfully" });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting lead {Id}", index);
                return StatusCode(500, new { status = "error", message = "An error occurred while deleting the lead" });
            }
        }

        #region SRO Transaction Data

        /// <summary>
        /// City-wide quarterly aggregation — reads directly from sro_transactions table.
        /// Returns: { "Q1 2023": { avg_price_sqft, total_volume, count }, ... }
        /// </summary>
        [HttpGet("sro/aggregate/city")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroCityAggregate()
        {
            _logger.LogInformation("GET /api/sro/aggregate/city — querying DB");
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;

                await using var conn = new Npgsql.NpgsqlConnection(connStr);
                var rows = await Dapper.SqlMapper.QueryAsync(conn, @"
                    SELECT quarter,
                           ROUND(AVG(price_per_sqft)::numeric, 0) AS avg_price_sqft,
                           SUM(mkt_value)                         AS total_volume,
                           COUNT(*)                               AS count
                    FROM   sro_transactions
                    WHERE  quarter IS NOT NULL AND price_per_sqft > 0
                    GROUP  BY quarter
                    ORDER  BY quarter");

                var result = new Dictionary<string, object>();
                foreach (var row in rows)
                {
                    var d = (IDictionary<string, object>)row;
                    result[(string)d["quarter"]] = new
                    {
                        avg_price_sqft = Convert.ToDouble(d["avg_price_sqft"]),
                        total_volume   = Convert.ToInt64(d["total_volume"]),
                        count          = Convert.ToInt32(d["count"])
                    };
                }
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroCityAggregate");
                return Ok(new Dictionary<string, object>());
            }
        }

        /// <summary>
        /// Per-locality quarterly aggregation.
        /// Returns: { "Kondapur": { "Q1 2023": {...}, ... }, ... }
        /// Optional ?locality= returns just that locality's map.
        /// </summary>
        [HttpGet("sro/aggregate/locality")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroLocalityAggregate([FromQuery] string? locality = null)
        {
            _logger.LogInformation("GET /api/sro/aggregate/locality locality={Loc}", locality);
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;

                await using var conn = new Npgsql.NpgsqlConnection(connStr);
                var sql = string.IsNullOrWhiteSpace(locality)
                    ? @"SELECT village, quarter,
                               ROUND(AVG(price_per_sqft)::numeric,0) AS avg_price_sqft,
                               SUM(mkt_value)                        AS total_volume,
                               COUNT(*)                              AS count
                        FROM   sro_transactions
                        WHERE  quarter IS NOT NULL AND price_per_sqft > 0
                        GROUP  BY village, quarter
                        ORDER  BY village, quarter"
                    : @"SELECT village, quarter,
                               ROUND(AVG(price_per_sqft)::numeric,0) AS avg_price_sqft,
                               SUM(mkt_value)                        AS total_volume,
                               COUNT(*)                              AS count
                        FROM   sro_transactions
                        WHERE  quarter IS NOT NULL AND price_per_sqft > 0
                          AND  LOWER(village) = LOWER(@locality)
                        GROUP  BY village, quarter
                        ORDER  BY quarter";

                var rows = await Dapper.SqlMapper.QueryAsync(conn, sql,
                    string.IsNullOrWhiteSpace(locality) ? null : new { locality });

                // Build nested map: village → quarter → stats
                var outer = new Dictionary<string, Dictionary<string, object>>();
                foreach (var row in rows)
                {
                    var d    = (IDictionary<string, object>)row;
                    var vil  = (string)(d["village"] ?? "Unknown");
                    var qtr  = (string)(d["quarter"] ?? "");
                    if (!outer.ContainsKey(vil)) outer[vil] = new Dictionary<string, object>();
                    outer[vil][qtr] = new
                    {
                        avg_price_sqft = Convert.ToDouble(d["avg_price_sqft"]),
                        total_volume   = Convert.ToInt64(d["total_volume"]),
                        count          = Convert.ToInt32(d["count"])
                    };
                }

                // If a specific locality was requested, return just its inner map
                if (!string.IsNullOrWhiteSpace(locality))
                {
                    var key = outer.Keys.FirstOrDefault(k =>
                        k.Equals(locality, StringComparison.OrdinalIgnoreCase));
                    return Ok(key != null ? outer[key] : new Dictionary<string, object>());
                }
                return Ok(outer);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroLocalityAggregate");
                return Ok(new Dictionary<string, object>());
            }
        }

        /// <summary>
        /// Top N localities by avg price/sqft — reads directly from DB.
        /// </summary>
        [HttpGet("sro/rank/price")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroPriceRank(
            [FromQuery] string? quarter = null, [FromQuery] int top = 10)
        {
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;
                await using var conn = new Npgsql.NpgsqlConnection(connStr);

                var whereClause = string.IsNullOrWhiteSpace(quarter)
                    ? "WHERE price_per_sqft > 0"
                    : "WHERE price_per_sqft > 0 AND quarter = @quarter";

                var rows = await Dapper.SqlMapper.QueryAsync(conn, $@"
                    SELECT village AS locality,
                           ROUND(AVG(price_per_sqft)::numeric, 0) AS avg_price_sqft,
                           COUNT(*) AS count
                    FROM   sro_transactions
                    {whereClause}
                    GROUP  BY village
                    ORDER  BY avg_price_sqft DESC
                    LIMIT  @top",
                    new { quarter, top });

                var rank = rows.Select(r =>
                {
                    var d = (IDictionary<string, object>)r;
                    return new
                    {
                        locality       = (string)(d["locality"] ?? ""),
                        avg_price_sqft = Convert.ToDouble(d["avg_price_sqft"]),
                        count          = Convert.ToInt32(d["count"])
                    };
                }).ToList();

                return Ok(new { quarter = quarter ?? "all", rank });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroPriceRank");
                return Ok(new { quarter = quarter ?? "all", rank = new List<object>() });
            }
        }

        /// <summary>
        /// Top N localities by total volume — reads directly from DB.
        /// </summary>
        [HttpGet("sro/rank/volume")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroVolumeRank(
            [FromQuery] string? quarter = null, [FromQuery] int top = 10)
        {
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;
                await using var conn = new Npgsql.NpgsqlConnection(connStr);

                var whereClause = string.IsNullOrWhiteSpace(quarter)
                    ? "WHERE price_per_sqft > 0"
                    : "WHERE price_per_sqft > 0 AND quarter = @quarter";

                var rows = await Dapper.SqlMapper.QueryAsync(conn, $@"
                    SELECT village AS locality,
                           SUM(mkt_value) AS total_volume,
                           COUNT(*)       AS count
                    FROM   sro_transactions
                    {whereClause}
                    GROUP  BY village
                    ORDER  BY total_volume DESC
                    LIMIT  @top",
                    new { quarter, top });

                var rank = rows.Select(r =>
                {
                    var d = (IDictionary<string, object>)r;
                    return new
                    {
                        locality     = (string)(d["locality"] ?? ""),
                        total_volume = Convert.ToInt64(d["total_volume"]),
                        count        = Convert.ToInt32(d["count"])
                    };
                }).ToList();

                return Ok(new { quarter = quarter ?? "all", rank });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroVolumeRank");
                return Ok(new { quarter = quarter ?? "all", rank = new List<object>() });
            }
        }

        /// <summary>
        /// Quarterly SRO transaction trend for a single RERA project matched by name.
        /// </summary>
        [HttpGet("sro/project/trend")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroProjectTrend([FromQuery] string name = "")
        {
            if (string.IsNullOrWhiteSpace(name))
                return BadRequest(new { error = "name is required" });
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;
                await using var conn = new Npgsql.NpgsqlConnection(connStr);

                // Fuzzy match: first word of project name vs apartment column
                var keyword = name.Split(' ').First().ToUpperInvariant();
                var rows = await Dapper.SqlMapper.QueryAsync(conn, @"
                    SELECT quarter,
                           ROUND(AVG(price_per_sqft)::numeric, 0) AS avg_price_sqft,
                           COUNT(*) AS count
                    FROM   sro_transactions
                    WHERE  UPPER(apartment) LIKE @pattern AND price_per_sqft > 0
                    GROUP  BY quarter
                    ORDER  BY quarter",
                    new { pattern = $"%{keyword}%" });

                var quarters = rows.Select(r =>
                {
                    var d = (IDictionary<string, object>)r;
                    return new
                    {
                        quarter        = (string)(d["quarter"] ?? ""),
                        avg_price_sqft = Convert.ToDouble(d["avg_price_sqft"]),
                        count          = Convert.ToInt32(d["count"])
                    };
                }).ToList();

                return Ok(new
                {
                    found                = quarters.Count > 0,
                    quarters,
                    total_transactions   = quarters.Sum(q => q.count),
                    matched_apartments   = new[] { name }
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroProjectTrend");
                return Ok(new { found = false, quarters = new List<object>() });
            }
        }

        /// <summary>
        /// SRO registration / sales status for a single RERA project.
        /// </summary>
        [HttpGet("sro/project/units")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> GetSroProjectUnits([FromQuery] string name = "")
        {
            if (string.IsNullOrWhiteSpace(name))
                return BadRequest(new { error = "name is required" });
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;
                await using var conn = new Npgsql.NpgsqlConnection(connStr);

                var keyword = name.Split(' ').First().ToUpperInvariant();
                var rows = await Dapper.SqlMapper.QueryAsync(conn, @"
                    SELECT quarter,
                           COUNT(*)                              AS count,
                           COUNT(DISTINCT flat_no)              AS unique_flats,
                           ROUND((SUM(mkt_value)/1e7)::numeric, 2) AS total_value_cr
                    FROM   sro_transactions
                    WHERE  UPPER(apartment) LIKE @pattern
                    GROUP  BY quarter
                    ORDER  BY quarter",
                    new { pattern = $"%{keyword}%" });

                var byQuarter = rows.Select(r =>
                {
                    var d = (IDictionary<string, object>)r;
                    return new
                    {
                        quarter         = (string)(d["quarter"] ?? ""),
                        count           = Convert.ToInt32(d["count"]),
                        unique_flats    = Convert.ToInt32(d["unique_flats"]),
                        total_value_cr  = Convert.ToDouble(d["total_value_cr"])
                    };
                }).ToList();

                var last = byQuarter.LastOrDefault();
                return Ok(new
                {
                    found                    = byQuarter.Count > 0,
                    total_registered         = byQuarter.Sum(q => q.count),
                    unique_flats_registered  = byQuarter.Sum(q => q.unique_flats),
                    total_value_cr           = byQuarter.Sum(q => q.total_value_cr),
                    by_quarter               = byQuarter,
                    recent_quarter           = last?.quarter ?? "",
                    recent_count             = last?.count ?? 0,
                    matched_apartments       = new[] { name }
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in GetSroProjectUnits");
                return Ok(new { found = false });
            }
        }

        /// <summary>
        /// Triggers SRO scraping — proxied through _pythonScraperClient.
        /// </summary>
        [HttpPost("sro/scrape")]
        public async Task<IActionResult> StartSroScrape([FromBody] JsonElement? body)
        {
            var payload = body.HasValue ? body.Value.GetRawText() : "{}";
            var json    = await _pythonScraperClient.StartSroScrapeAsync(payload);
            return Content(json, "application/json");
        }

        /// <summary>
        /// SRO scraping status — proxied through _pythonScraperClient.
        /// </summary>
        [HttpGet("sro/scrape/status")]
        public async Task<IActionResult> GetSroScrapeStatus()
        {
            var json = await _pythonScraperClient.GetSroScrapeStatusAsync();
            return Content(json, "application/json");
        }

        #endregion

        #region Ready Reckoner (Unit Rate) Scraping

        /// <summary>
        /// Starts Ready Reckoner unit-rate scraping — proxied through _pythonScraperClient.
        /// </summary>
        [HttpPost("rr_scrape")]
        public async Task<IActionResult> StartRrScrape([FromBody] JsonElement? body)
        {
            var payload = body.HasValue ? body.Value.GetRawText() : "{}";
            var json    = await _pythonScraperClient.StartRrScrapeAsync(payload);
            return Content(json, "application/json");
        }

        /// <summary>
        /// Gets Ready Reckoner scraping status — proxied through _pythonScraperClient.
        /// </summary>
        [HttpGet("rr_scrape/status")]
        public async Task<IActionResult> GetRrScrapeStatus()
        {
            var json = await _pythonScraperClient.GetRrScrapeStatusAsync();
            return Content(json, "application/json");
        }

        /// <summary>
        /// Stops an in-progress Ready Reckoner scrape — proxied through _pythonScraperClient.
        /// </summary>
        [HttpPost("rr_scrape/stop")]
        public async Task<IActionResult> StopRrScrape()
        {
            var json = await _pythonScraperClient.StopRrScrapeAsync();
            return Content(json, "application/json");
        }

        /// <summary>
        /// Returns scraped unit rates. Optional ?district=&mandal=&locality= filters.
        /// Reads unit_rates.json written by Python scraper.
        /// </summary>
        [HttpGet("unit_rates")]
        public async Task<IActionResult> GetUnitRates(
            [FromQuery] string? district = null,
            [FromQuery] string? mandal   = null,
            [FromQuery] string? locality = null)
        {
            try
            {
                var projectRoot = Directory.GetCurrentDirectory();
                var parentDir   = Directory.GetParent(projectRoot)?.FullName ?? projectRoot;
                var path        = Path.Combine(parentDir, "backend", "scraped_projects", "unit_rates.json");

                if (!System.IO.File.Exists(path))
                    return Ok(new { scraped_at = (string?)null, total = 0, records = new List<object>() });

                var json = await System.IO.File.ReadAllTextAsync(path);
                using var doc = JsonDocument.Parse(json);

                var records = doc.RootElement
                    .GetProperty("records")
                    .EnumerateArray()
                    .Where(r =>
                    {
                        if (!string.IsNullOrEmpty(district) &&
                            !GetStr(r, "district").Contains(district, StringComparison.OrdinalIgnoreCase))
                            return false;
                        if (!string.IsNullOrEmpty(mandal) &&
                            !GetStr(r, "mandal").Contains(mandal, StringComparison.OrdinalIgnoreCase))
                            return false;
                        if (!string.IsNullOrEmpty(locality) &&
                            !GetStr(r, "locality").Contains(locality, StringComparison.OrdinalIgnoreCase))
                            return false;
                        return true;
                    })
                    .Select(r => (object)r.Clone())
                    .ToList();

                var scrapedAt = doc.RootElement.TryGetProperty("scraped_at", out var sa)
                    ? sa.GetString() : null;

                return Ok(new { scraped_at = scrapedAt, total = records.Count, records });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error reading unit_rates.json");
                return StatusCode(500, new { error = ex.Message });
            }
        }

        /// <summary>
        /// Returns a mandal-level summary of avg unit rates grouped by mandal (reads from DB).
        /// </summary>
        [HttpGet("unit_rates/summary")]
        public async Task<IActionResult> GetUnitRatesSummary()
        {
            try
            {
                var connStr = HttpContext.RequestServices
                    .GetRequiredService<IConfiguration>()
                    .GetConnectionString("DefaultConnection")!;
                await using var conn = new Npgsql.NpgsqlConnection(connStr);

                var rows = await Dapper.SqlMapper.QueryAsync(conn, @"
                    SELECT mandal,
                           district,
                           MAX(locality) AS locality,
                           ROUND(AVG(CASE WHEN search_type='apartment' THEN unit_rate_sqft END)::numeric,0) AS apartment_rate_sqft,
                           ROUND(AVG(CASE WHEN search_type='land'      THEN unit_rate_sqft END)::numeric,0) AS land_rate_sqft,
                           ROUND(AVG(unit_rate_sqft)::numeric,0)                                           AS avg_rate_sqft,
                           COUNT(*) AS count
                    FROM   unit_rates
                    WHERE  unit_rate_sqft > 100
                    GROUP  BY mandal, district
                    ORDER  BY avg_rate_sqft DESC NULLS LAST");

                var summary = rows.Select(r =>
                {
                    var d = (IDictionary<string, object>)r;
                    return new
                    {
                        mandal              = (string)(d["mandal"] ?? ""),
                        locality            = (string)(d["locality"] ?? d["mandal"] ?? ""),
                        district            = (string)(d["district"] ?? ""),
                        apartment_rate_sqft = d["apartment_rate_sqft"] == null ? (double?)null : Convert.ToDouble(d["apartment_rate_sqft"]),
                        land_rate_sqft      = d["land_rate_sqft"]      == null ? (double?)null : Convert.ToDouble(d["land_rate_sqft"]),
                        avg_rate_sqft       = d["avg_rate_sqft"]       == null ? 0.0 : Convert.ToDouble(d["avg_rate_sqft"]),
                        count               = Convert.ToInt32(d["count"])
                    };
                }).ToList();

                return Ok(summary);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error computing unit rate summary from DB");
                return Ok(new List<object>());
            }
        }

        private static string GetStr(JsonElement el, string key) =>
            el.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String
                ? v.GetString() ?? "" : "";

        #endregion

        #region Python Service Status

        /// <summary>
        /// Checks if Python Flask service is available
        /// </summary>
        [HttpGet("python/status")]
        [ProducesResponseType(typeof(object), 200)]
        public async Task<IActionResult> CheckPythonServiceStatus()
        {
            try
            {
                _logger.LogInformation("GET /api/python/status");
                
                var isAvailable = await _pythonScraperClient.IsServiceAvailableAsync();
                
                return Ok(new 
                { 
                    status = isAvailable ? "available" : "unavailable",
                    service = "Python Flask Scraper",
                    timestamp = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking Python service status");
                return Ok(new 
                { 
                    status = "unavailable",
                    service = "Python Flask Scraper",
                    error = ex.Message,
                    timestamp = DateTime.UtcNow
                });
            }
        }

        #endregion
    }
}
