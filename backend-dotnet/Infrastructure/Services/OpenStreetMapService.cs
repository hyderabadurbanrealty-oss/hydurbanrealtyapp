using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using Microsoft.Extensions.Options;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Service for OpenStreetMap operations including geocoding and POI data
    /// Follows Single Responsibility - handles OSM operations only
    /// 100% FREE - No API key required
    /// </summary>
    public class OpenStreetMapService : IOpenStreetMapService
    {
        private readonly HttpClient _httpClient;
        private readonly OpenStreetMapSettings _settings;
        private readonly ILogger<OpenStreetMapService> _logger;
        private DateTime _lastRequestTime = DateTime.MinValue;

        // Fallback Overpass mirrors tried in order when the primary times out
        private static readonly string[] OverpassMirrors = new[]
        {
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        };

        // Total wall-clock budget for one POI fetch (all retries combined)
        private static readonly TimeSpan PoiBudget = TimeSpan.FromSeconds(55);

        public OpenStreetMapService(
            IOptions<OpenStreetMapSettings> settings,
            ILogger<OpenStreetMapService> logger)
        {
            _settings = settings?.Value ?? throw new ArgumentNullException(nameof(settings));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));

            // Use a generous timeout; per-attempt CTS further controls individual requests
            _httpClient = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(Math.Max(_settings.TimeoutSeconds, 30))
            };
            _httpClient.DefaultRequestHeaders.Add("User-Agent",
                string.IsNullOrWhiteSpace(_settings.UserAgent)
                    ? "HyderabadUrbanReality/1.0 (contact: admin@hydurban.in)"
                    : _settings.UserAgent);
        }

        /// <inheritdoc />
        public async Task<Dictionary<string, object>> GetNeighborhoodDataAsync(
            double latitude, 
            double longitude, 
            string district)
        {
            var result = new Dictionary<string, object>
            {
                ["latitude"] = latitude,
                ["longitude"] = longitude,
                ["district"] = district
            };

            try
            {
                _logger.LogInformation("Fetching neighborhood data for {Lat}, {Lng}", latitude, longitude);
                
                // Validate coordinates
                if (!ValidateCoordinatesForDistrict(latitude, longitude, district))
                {
                    _logger.LogWarning("Coordinates may be outside expected district bounds");
                }
                
                // Fetch Points of Interest using Overpass API
                var pois = await FetchPointsOfInterestAsync(latitude, longitude);
                result["points_of_interest"] = pois;
                
                _logger.LogInformation("Successfully fetched neighborhood data");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error fetching neighborhood data");
                result["error"] = ex.Message;
            }

            return result;
        }

        /// <inheritdoc />
        public async Task<(double latitude, double longitude)?> GeocodeAddressAsync(string address)
        {
            if (string.IsNullOrWhiteSpace(address))
            {
                throw new ArgumentException("Address cannot be empty", nameof(address));
            }

            try
            {
                _logger.LogInformation("Geocoding address: {Address}", address);
                
                // Respect Nominatim rate limit (1 request per second)
                await RateLimitAsync();
                
                var queryParams = new Dictionary<string, string>
                {
                    ["q"] = address,
                    ["format"] = "json",
                    ["limit"] = "3",
                    ["countrycodes"] = "in" // Restrict to India
                };
                
                var queryString = string.Join("&", queryParams.Select(kvp => 
                    $"{Uri.EscapeDataString(kvp.Key)}={Uri.EscapeDataString(kvp.Value)}"));
                
                var url = $"{_settings.NominatimUrl}?{queryString}";
                var response = await _httpClient.GetAsync(url);
                response.EnsureSuccessStatusCode();
                
                var jsonContent = await response.Content.ReadAsStringAsync();
                var results = JsonConvert.DeserializeObject<JArray>(jsonContent);
                
                if (results != null && results.Count > 0)
                {
                    var firstResult = results[0];
                    var lat = firstResult["lat"]?.ToObject<double>() ?? 0;
                    var lon = firstResult["lon"]?.ToObject<double>() ?? 0;
                    
                    _logger.LogInformation("Geocoded to: {Lat}, {Lon}", lat, lon);
                    return (lat, lon);
                }
                
                _logger.LogWarning("No geocoding results for address: {Address}", address);
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error geocoding address: {Address}", address);
                return null;
            }
        }

        /// <summary>
        /// Smart multi-strategy geocoding with fallback
        /// Tries multiple address combinations from most to least specific
        /// Returns the first valid result
        /// </summary>
        public async Task<(double latitude, double longitude)?> SmartGeocodeAsync(
            string houseNumber = "",
            string buildingName = "",
            string streetName = "",
            string locality = "",
            string mandal = "",
            string district = "",
            string pinCode = "")
        {
            var strategies = new List<(string strategyName, string address)>();
            
            // Strategy 1: Full detailed address
            if (!string.IsNullOrWhiteSpace(houseNumber) || !string.IsNullOrWhiteSpace(buildingName))
            {
                var parts = new[] { houseNumber, buildingName, streetName, locality, mandal, district, pinCode, "Telangana", "India" }
                    .Where(p => !string.IsNullOrWhiteSpace(p));
                strategies.Add(("Full address", string.Join(", ", parts)));
            }
            
            // Strategy 2: Locality + PIN + District (often most accurate for Indian addresses)
            if (!string.IsNullOrWhiteSpace(locality) && !string.IsNullOrWhiteSpace(pinCode) && !string.IsNullOrWhiteSpace(district))
            {
                strategies.Add(("Locality+PIN", $"{locality}, {pinCode}, {district}, Telangana, India"));
            }
            
            // Strategy 3: Locality + Mandal + District
            if (!string.IsNullOrWhiteSpace(locality) && !string.IsNullOrWhiteSpace(district))
            {
                var parts = new[] { locality, mandal, district, "Telangana", "India" }
                    .Where(p => !string.IsNullOrWhiteSpace(p));
                strategies.Add(("Locality+District", string.Join(", ", parts)));
            }
            
            // Strategy 4: PIN code only (reliable for general area)
            if (!string.IsNullOrWhiteSpace(pinCode))
            {
                strategies.Add(("PIN only", $"{pinCode}, Telangana, India"));
            }
            
            // Strategy 5: District center as last resort
            if (!string.IsNullOrWhiteSpace(district))
            {
                strategies.Add(("District center", $"{district}, Telangana, India"));
            }
            
            // Try each strategy
            foreach (var (strategyName, address) in strategies)
            {
                _logger.LogDebug("Trying {Strategy}: {Address}", strategyName, address);
                
                var coords = await GeocodeAddressAsync(address);
                if (coords.HasValue && ValidateCoordinatesForDistrict(coords.Value.latitude, coords.Value.longitude, district))
                {
                    _logger.LogInformation("Successfully geocoded using {Strategy}", strategyName);
                    return coords;
                }
                
                await Task.Delay(500); // Small delay between attempts
            }
            
            _logger.LogWarning("All geocoding strategies failed");
            return null;
        }

        /// <inheritdoc />
        public double CalculateDistance(double lat1, double lon1, double lat2, double lon2)
        {
            // Haversine formula for calculating distance between coordinates
            const double R = 6371; // Earth's radius in kilometers
            
            var dLat = DegreesToRadians(lat2 - lat1);
            var dLon = DegreesToRadians(lon2 - lon1);
            
            var a = Math.Sin(dLat / 2) * Math.Sin(dLat / 2) +
                    Math.Cos(DegreesToRadians(lat1)) * Math.Cos(DegreesToRadians(lat2)) *
                    Math.Sin(dLon / 2) * Math.Sin(dLon / 2);
            
            var c = 2 * Math.Atan2(Math.Sqrt(a), Math.Sqrt(1 - a));
            var distance = R * c;
            
            return Math.Round(distance, 2);
        }

        #region Private Helper Methods

        /// <summary>
        /// Validates if coordinates are within reasonable bounds for a district
        /// Approximate boundaries for metro districts:
        /// - Hyderabad: 17.2-17.6°N, 78.2-78.7°E
        /// - Ranga Reddy: 16.9-17.5°N, 77.9-78.6°E
        /// - Sangareddy: 17.4-18.2°N, 77.8-78.4°E
        /// </summary>
        private bool ValidateCoordinatesForDistrict(double lat, double lng, string district)
        {
            var districtLower = district?.ToLowerInvariant() ?? string.Empty;
            
            // Check if within Telangana overall bounds
            if (lat < 16.0 || lat > 19.0 || lng < 77.0 || lng > 81.0)
            {
                return false;
            }
            
            // Specific district validation
            if (districtLower.Contains("hyderabad"))
            {
                return lat >= 17.2 && lat <= 17.6 && lng >= 78.2 && lng <= 78.7;
            }
            else if (districtLower.Contains("ranga") || districtLower.Contains("reddy"))
            {
                return lat >= 16.9 && lat <= 17.5 && lng >= 77.9 && lng <= 78.6;
            }
            else if (districtLower.Contains("sangareddy") || districtLower.Contains("sanga"))
            {
                return lat >= 17.4 && lat <= 18.2 && lng >= 77.8 && lng <= 78.4;
            }
            
            // If district not recognized, accept if within Telangana
            return true;
        }

        /// <summary>
        /// Fetches Points of Interest using Overpass API with mirror fallback and per-attempt timeout.
        /// Tries the primary URL first, then falls back to mirror URLs if a timeout/error occurs.
        /// </summary>
        private async Task<Dictionary<string, List<Dictionary<string, object>>>> FetchPointsOfInterestAsync(
            double latitude,
            double longitude)
        {
            var pois = new Dictionary<string, List<Dictionary<string, object>>>();

            try
            {
                await RateLimitAsync();

                var radiusMeters = _settings.DefaultRadiusKm * 1000;

                // Overpass query with a 20 s server-side timeout (generous but not unbounded)
                var query = $@"
                    [out:json][timeout:20];
                    (
                      node[""amenity""=""school""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""hospital""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""clinic""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""bank""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""atm""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""restaurant""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""cafe""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""fast_food""](around:{radiusMeters},{latitude},{longitude});
                      node[""amenity""=""cinema""](around:{radiusMeters},{latitude},{longitude});
                      node[""shop""=""supermarket""](around:{radiusMeters},{latitude},{longitude});
                      node[""shop""=""mall""](around:{radiusMeters},{latitude},{longitude});
                      node[""public_transport""=""station""](around:{radiusMeters},{latitude},{longitude});
                      node[""leisure""=""park""](around:{radiusMeters},{latitude},{longitude});
                      way[""amenity""=""school""](around:{radiusMeters},{latitude},{longitude});
                      way[""amenity""=""hospital""](around:{radiusMeters},{latitude},{longitude});
                      way[""shop""=""mall""](around:{radiusMeters},{latitude},{longitude});
                      way[""leisure""=""park""](around:{radiusMeters},{latitude},{longitude});
                    );
                    out center body;
                ";

                // Build the ordered list of endpoints to try: configured primary + mirrors
                var primaryUrl = string.IsNullOrWhiteSpace(_settings.OverpassUrl)
                    ? OverpassMirrors[0]
                    : _settings.OverpassUrl;
                var endpoints = new[] { primaryUrl }
                    .Concat(OverpassMirrors.Where(m => m != primaryUrl))
                    .ToArray();

                // Per-attempt wall-clock budget: 22 s each (slightly more than server timeout)
                const int perAttemptSeconds = 22;

                foreach (var endpoint in endpoints)
                {
                    try
                    {
                        _logger.LogDebug("Trying Overpass endpoint: {Url}", endpoint);

                        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(perAttemptSeconds));

                        var content = new FormUrlEncodedContent(new[]
                        {
                            new KeyValuePair<string, string>("data", query)
                        });

                        var response = await _httpClient.PostAsync(endpoint, content, cts.Token);

                        if (!response.IsSuccessStatusCode)
                        {
                            _logger.LogWarning("Overpass {Url} returned {Status} — trying next mirror",
                                endpoint, response.StatusCode);
                            continue;
                        }

                        var jsonContent = await response.Content.ReadAsStringAsync(cts.Token);

                        if (string.IsNullOrWhiteSpace(jsonContent))
                        {
                            _logger.LogWarning("Overpass {Url} returned empty body — trying next mirror", endpoint);
                            continue;
                        }

                        var data = JsonConvert.DeserializeObject<JObject>(jsonContent);
                        var elements = data?["elements"] as JArray;

                        if (elements != null)
                        {
                            foreach (var element in elements)
                            {
                                try
                                {
                                    var tags = element["tags"] as JObject;
                                    if (tags == null) continue;

                                    var name = tags["name"]?.ToString()
                                            ?? tags["operator"]?.ToString()
                                            ?? "Unnamed";
                                    if (name == "Unnamed") continue;

                                    double elemLat, elemLon;
                                    if (element["type"]?.ToString() == "node")
                                    {
                                        elemLat = element["lat"]?.ToObject<double>() ?? 0;
                                        elemLon = element["lon"]?.ToObject<double>() ?? 0;
                                    }
                                    else if (element["center"] != null)
                                    {
                                        elemLat = element["center"]?["lat"]?.ToObject<double>() ?? 0;
                                        elemLon = element["center"]?["lon"]?.ToObject<double>() ?? 0;
                                    }
                                    else continue;

                                    if (elemLat == 0 || elemLon == 0) continue;

                                    var amenity = tags["amenity"]?.ToString()
                                               ?? tags["shop"]?.ToString()
                                               ?? tags["leisure"]?.ToString()
                                               ?? tags["public_transport"]?.ToString()
                                               ?? "other";

                                    var distance = CalculateDistance(latitude, longitude, elemLat, elemLon);

                                    var poi = new Dictionary<string, object>
                                    {
                                        ["name"]         = name,
                                        ["type"]         = amenity,
                                        ["distance"]     = distance,
                                        ["distanceUnit"] = "km",
                                        ["rating"]       = 0,
                                        ["address"]      = tags["addr:full"]?.ToString() ?? tags["addr:street"]?.ToString() ?? "",
                                        ["coordinates"]  = new Dictionary<string, double>
                                        {
                                            ["lat"] = elemLat,
                                            ["lng"] = elemLon
                                        },
                                        ["extra"] = new Dictionary<string, string>
                                        {
                                            ["operator"] = tags["operator"]?.ToString() ?? "",
                                            ["website"]  = tags["website"]?.ToString() ?? "",
                                            ["phone"]    = tags["phone"]?.ToString() ?? ""
                                        }
                                    };

                                    if (!pois.ContainsKey(amenity))
                                        pois[amenity] = new List<Dictionary<string, object>>();

                                    pois[amenity].Add(poi);
                                }
                                catch (Exception ex)
                                {
                                    _logger.LogDebug(ex, "Error parsing POI element — skipping");
                                }
                            }

                            // Sort each category by distance and cap at 4
                            foreach (var category in pois.Keys.ToList())
                            {
                                pois[category] = pois[category]
                                    .OrderBy(p => (double)p["distance"])
                                    .Take(4)
                                    .ToList();
                            }

                            _logger.LogInformation("Overpass returned {Count} POI categories via {Url}",
                                pois.Count, endpoint);
                        }

                        // Successful response — stop trying mirrors
                        return pois;
                    }
                    catch (OperationCanceledException)
                    {
                        _logger.LogWarning("Overpass {Url} timed out after {Sec}s — trying next mirror",
                            endpoint, perAttemptSeconds);
                    }
                    catch (HttpRequestException ex)
                    {
                        _logger.LogWarning(ex, "Overpass {Url} connection error — trying next mirror", endpoint);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Overpass {Url} unexpected error — trying next mirror", endpoint);
                    }
                }

                _logger.LogWarning("All Overpass mirrors exhausted — returning empty POI set");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in FetchPointsOfInterestAsync");
            }

            return pois;
        }

        /// <summary>
        /// Fetches nearby schools (max 3km radius)
        /// </summary>
        public async Task<List<Dictionary<string, object>>> FetchSchoolsAsync(double latitude, double longitude)
        {
            return await SearchNearbyPlacesAsync(latitude, longitude, new Dictionary<string, string> { ["amenity"] = "school" }, 3000);
        }

        /// <summary>
        /// Fetches nearby hospitals (max 5km radius)
        /// </summary>
        public async Task<List<Dictionary<string, object>>> FetchHospitalsAsync(double latitude, double longitude)
        {
            return await SearchNearbyPlacesAsync(latitude, longitude, new Dictionary<string, string> { ["amenity"] = "hospital" }, 5000);
        }

        /// <summary>
        /// Search for nearby places using Overpass API with per-attempt timeout and mirror fallback.
        /// </summary>
        private async Task<List<Dictionary<string, object>>> SearchNearbyPlacesAsync(
            double lat,
            double lng,
            Dictionary<string, string> placeTags,
            int radius = 5000,
            int maxRetries = 2)
        {
            var places = new List<Dictionary<string, object>>();

            try
            {
                var tagFilters = string.Join("", placeTags.Select(kvp => $"[\"{kvp.Key}\"=\"{kvp.Value}\"]"));

                var query = $@"
                    [out:json][timeout:20];
                    (
                      node{tagFilters}(around:{radius},{lat},{lng});
                      way{tagFilters}(around:{radius},{lat},{lng});
                    );
                    out center body;
                ";

                var primaryUrl = string.IsNullOrWhiteSpace(_settings.OverpassUrl)
                    ? OverpassMirrors[0]
                    : _settings.OverpassUrl;
                var endpoints = new[] { primaryUrl }
                    .Concat(OverpassMirrors.Where(m => m != primaryUrl))
                    .ToArray();

                const int perAttemptSeconds = 22;

                foreach (var endpoint in endpoints)
                {
                    try
                    {
                        await Task.Delay(500);

                        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(perAttemptSeconds));

                        var content = new FormUrlEncodedContent(new[]
                        {
                            new KeyValuePair<string, string>("data", query)
                        });

                        var response = await _httpClient.PostAsync(endpoint, content, cts.Token);
                        if (!response.IsSuccessStatusCode) continue;

                        var jsonContent = await response.Content.ReadAsStringAsync(cts.Token);
                        if (string.IsNullOrWhiteSpace(jsonContent)) continue;

                        var data = JsonConvert.DeserializeObject<JObject>(jsonContent);
                        var elements = data?["elements"] as JArray;

                        if (elements != null)
                        {
                            foreach (var element in elements)
                            {
                                var tags = element["tags"] as JObject;
                                if (tags == null) continue;

                                var name = tags["name"]?.ToString() ?? tags["operator"]?.ToString() ?? "Unnamed";
                                if (name == "Unnamed") continue;

                                double elemLat = 0, elemLon = 0;
                                if (element["type"]?.ToString() == "node")
                                {
                                    elemLat = element["lat"]?.ToObject<double>() ?? 0;
                                    elemLon = element["lon"]?.ToObject<double>() ?? 0;
                                }
                                else if (element["center"] != null)
                                {
                                    elemLat = element["center"]?["lat"]?.ToObject<double>() ?? 0;
                                    elemLon = element["center"]?["lon"]?.ToObject<double>() ?? 0;
                                }

                                if (elemLat == 0 || elemLon == 0) continue;

                                var distance = CalculateDistance(lat, lng, elemLat, elemLon);

                                places.Add(new Dictionary<string, object>
                                {
                                    ["name"]         = name,
                                    ["type"]         = placeTags.Values.FirstOrDefault() ?? "place",
                                    ["distance"]     = distance,
                                    ["distanceUnit"] = "km",
                                    ["rating"]       = 0,
                                    ["address"]      = tags["addr:full"]?.ToString() ?? "",
                                    ["coordinates"]  = new { lat = elemLat, lng = elemLon }
                                });
                            }
                        }

                        // Success — stop trying mirrors
                        break;
                    }
                    catch (OperationCanceledException)
                    {
                        _logger.LogWarning("SearchNearbyPlaces: {Url} timed out — trying next mirror", endpoint);
                    }
                    catch (HttpRequestException ex)
                    {
                        _logger.LogWarning(ex, "SearchNearbyPlaces: {Url} connection error — trying next mirror", endpoint);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "SearchNearbyPlaces: {Url} unexpected error", endpoint);
                    }
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in SearchNearbyPlacesAsync");
            }

            return places.OrderBy(p => (double)p["distance"]).Take(10).ToList();
        }

        /// <summary>
        /// Ensures rate limiting for OSM APIs
        /// Nominatim requires max 1 request per second
        /// </summary>
        private async Task RateLimitAsync()
        {
            var timeSinceLastRequest = DateTime.UtcNow - _lastRequestTime;
            var minInterval = TimeSpan.FromSeconds(_settings.RateLimitSeconds);
            
            if (timeSinceLastRequest < minInterval)
            {
                var delay = minInterval - timeSinceLastRequest;
                await Task.Delay(delay);
            }
            
            _lastRequestTime = DateTime.UtcNow;
        }

        /// <summary>
        /// Converts degrees to radians
        /// </summary>
        private double DegreesToRadians(double degrees)
        {
            return degrees * Math.PI / 180.0;
        }

        #endregion

        public void Dispose()
        {
            _httpClient?.Dispose();
        }
    }
}
