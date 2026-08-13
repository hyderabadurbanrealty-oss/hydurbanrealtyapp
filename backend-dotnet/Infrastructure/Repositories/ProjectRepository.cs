using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using Microsoft.Extensions.Options;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    /// <summary>
    /// Repository for project data operations
    /// Follows Single Responsibility - handles data access only
    /// Implements Repository Pattern for data abstraction
    /// </summary>
    public class ProjectRepository : IProjectRepository
    {
        private readonly string _scrapedProjectsPath;
        private readonly string[] _shortlistedFields;
        private readonly ILogger<ProjectRepository> _logger;

        public ProjectRepository(
            IOptions<AppSettings> appSettings,
            ILogger<ProjectRepository> logger)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            
            var basePath = Directory.GetCurrentDirectory();
            _scrapedProjectsPath = Path.Combine(basePath, appSettings.Value.ScrapedProjectsPath);
            
            _shortlistedFields = new[]
            {
                // Project Basic Info
                "Project Name", "Project Status", "Project Type", "Approved Date", 
                "Proposed Date of Completion", "Revised Proposed Date of Completion",
                
                // Area Details
                "Total Area(In sqmts)", "Net Area(In sqmts)", "Approved Built up Area (In Sqmts)", 
                "Mortgage Area (In Sqmts)",
                
                // Boundaries
                "Boundaries East", "Boundaries West", "Boundaries North", "Boundaries South",
                
                // Location
                "State", "District", "Mandal", "Village/City/Town", "Pin Code", "Street", 
                "Locality", "Land mark",
                
                // Developer/Promoter Info
                "Name", "Organization Type", "Do you have any Past Experience ?", 
                "Any criminal or police case/ cases pending ?",
                
                // Approvals & Legal
                "Authority Name", "Plan Approval Number", "Sy.No/TS No.", 
                "Litigations related to the project ?",
                "Are there any Promoter(Land Owner/ Investor) (as defined by Telangana RERA Order) in the project ?",
                
                // Bank Details
                "Bank Name", "Branch Name", "Bank A/c Number", "IFSC Code",
                
                // Building Details
                "Total Building Units (as per approved plan)", "Proposed Building Units(as per agreement)",
                "Is the project an MSB or a High-Rise?"
            };
        }

        /// <inheritdoc />
        public async Task<IEnumerable<Dictionary<string, object>>> GetAllProjectsAsync()
        {
            var projects = new List<Dictionary<string, object>>();

            try
            {
                if (!Directory.Exists(_scrapedProjectsPath))
                {
                    _logger.LogWarning("Scraped projects path does not exist: {Path}", _scrapedProjectsPath);
                    return projects;
                }

                var directories = Directory.GetDirectories(_scrapedProjectsPath);
                
                foreach (var subdir in directories)
                {
                    var project = await LoadProjectFromDirectoryAsync(subdir);
                    if (project != null)
                    {
                        projects.Add(project);
                    }
                }

                _logger.LogInformation("Successfully loaded {Count} projects", projects.Count);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading projects from path: {Path}", _scrapedProjectsPath);
                throw;
            }

            return projects;
        }

        /// <inheritdoc />
        public async Task<Dictionary<string, object>?> GetProjectByIdAsync(string projectId)
        {
            if (string.IsNullOrWhiteSpace(projectId))
            {
                throw new ArgumentException("Project ID cannot be null or empty", nameof(projectId));
            }

            try
            {
                var projectPath = Path.Combine(_scrapedProjectsPath, projectId);
                
                if (!Directory.Exists(projectPath))
                {
                    _logger.LogWarning("Project directory not found: {ProjectId}", projectId);
                    return null;
                }

                return await LoadProjectFromDirectoryAsync(projectPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading project: {ProjectId}", projectId);
                throw;
            }
        }

        /// <inheritdoc />
        public Task<bool> ProjectExistsAsync(string projectId)
        {
            if (string.IsNullOrWhiteSpace(projectId))
            {
                return Task.FromResult(false);
            }

            var projectPath = Path.Combine(_scrapedProjectsPath, projectId);
            return Task.FromResult(Directory.Exists(projectPath));
        }

        /// <inheritdoc />
        public async Task<IEnumerable<Dictionary<string, object>>> GetProjectsByPinCodeAsync(string pinCode)
        {
            var allProjects = await GetAllProjectsAsync();
            return allProjects.Where(p =>
                p.TryGetValue("pinCode", out var pc) && pc?.ToString() == pinCode ||
                p.TryGetValue("Pin Code", out var pc2) && pc2?.ToString() == pinCode);
        }

        #region Private Helper Methods

        /// <summary>
        /// Loads project data from a directory
        /// Follows Open/Closed Principle - can extend without modifying
        /// </summary>
        private async Task<Dictionary<string, object>?> LoadProjectFromDirectoryAsync(string directoryPath)
        {
            try
            {
                var jsonPath = Path.Combine(directoryPath, "view_page_data.json");

                if (!File.Exists(jsonPath))
                {
                    _logger.LogDebug("JSON file not found in directory: {Path}", directoryPath);
                    return null;
                }

                var jsonContent = await File.ReadAllTextAsync(jsonPath);
                var data = JsonConvert.DeserializeObject<JObject>(jsonContent);

                if (data == null)
                {
                    _logger.LogWarning("Failed to deserialize JSON from: {Path}", jsonPath);
                    return null;
                }

                var project = ExtractFields(data);
                project["id"] = Path.GetFileName(directoryPath);

                // Aggregate Floor Breakdown rows (real flat count, saleable area, bookings)
                ExtractFloorBreakdownStats(data, project);

                // Pass raw Floor Breakdown and Building Tower Details arrays to frontend.
                // Convert to List<Dictionary<string,string>> so System.Text.Json can serialize them.
                var floorBreakdownArr = data["Floor Breakdown"] as JArray;
                if (floorBreakdownArr != null)
                {
                    var floorList = floorBreakdownArr
                        .OfType<JObject>()
                        .Select(row => row.Properties()
                            .ToDictionary(p => p.Name, p => p.Value?.ToString() ?? ""))
                        .ToList();
                    if (floorList.Count > 0)
                        project["Floor Breakdown"] = floorList;
                }

                var towerDetailsArr = data["Building Tower Details"] as JArray;
                if (towerDetailsArr != null)
                {
                    var towerList = towerDetailsArr
                        .OfType<JObject>()
                        .Select(row => row.Properties()
                            .ToDictionary(p => p.Name, p => p.Value?.ToString() ?? ""))
                        .Where(row =>
                        {
                            // Drop blob rows (embedded floor breakdown text > 200 chars in any cell)
                            if (row.Values.Any(v => v.Length > 200)) return false;
                            // Drop rows whose 'Name' cell is floor breakdown signal or True/False
                            var name = row.TryGetValue("Name", out var n) ? n.ToLowerInvariant() : "";
                            if (name == "true" || name == "false") return false;
                            if (name.Contains("floor id") || name.Contains("saleable area") || name.Contains("mortgage area")) return false;
                            // Drop construction-progress task rows embedded in tower table (Name is a bare number like "100")
                            if (double.TryParse(name, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out _)) return false;
                            // Drop repeated header rows (Sr.No. is non-numeric text)
                            var srNo = row.TryGetValue("Sr.No.", out var s) ? s.Trim() : "";
                            if (!string.IsNullOrEmpty(srNo) && !int.TryParse(srNo, out _)) return false;
                            return true;
                        })
                        .ToList();
                    if (towerList.Count > 0)
                        project["Building Tower Details"] = towerList;
                }

                // availableDocuments is written directly into view_page_data.json by the scraper
                // No need to scan disk — just pass it through if present
                if (data["availableDocuments"] != null)
                {
                    project["scrapedDocuments"] = data["availableDocuments"]!
                        .ToObject<List<string>>() ?? new List<string>();
                }
                else
                {
                    project["scrapedDocuments"] = new List<string>();
                }

                // Merge pricing.json if present (admin-entered pricing data)
                var pricingPath = Path.Combine(directoryPath, "pricing.json");
                if (File.Exists(pricingPath))
                {
                    try
                    {
                        var pricingJson = await File.ReadAllTextAsync(pricingPath);
                        var pricing = JsonConvert.DeserializeObject<object>(pricingJson);
                        if (pricing != null)
                            project["pricing"] = pricing;
                    }
                    catch
                    {
                        // pricing.json malformed — skip silently
                    }
                }

                return project;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading project from directory: {Path}", directoryPath);
                return null;
            }
        }

        /// <summary>
        /// Aggregates Floor Breakdown rows to derive real flat count, saleable area and booking stats.
        /// These are stored as flat scalar fields on the project dict so CalculateOccupancyDensity
        /// can use them directly without needing to re-parse the JObject.
        /// </summary>
        private void ExtractFloorBreakdownStats(JObject data, Dictionary<string, object> project)
        {
            var floorBreakdown = data["Floor Breakdown"] as JArray;
            if (floorBreakdown == null || !floorBreakdown.HasValues) return;

            int totalFlats = 0;
            int totalBooked = 0;
            double totalSaleableArea = 0;

            foreach (var row in floorBreakdown)
            {
                // Only process rows that have actual floor breakdown fields
                // (not developer track record rows which have "Project Name", "Type of Project" etc.)
                bool hasAptType = row["Apartment Type"] != null;
                bool hasFloorId = row["Floor ID"] != null;
                bool hasSaleableArea = row["Saleable Area (in Sqmts)"] != null || row["Saleable Area (In Sqmts)"] != null;
                if (!hasAptType && !hasFloorId && !hasSaleableArea) continue;

                var unitsStr = row["Number of Apartment"]?.ToString()
                            ?? row["Number of Apartments"]?.ToString();
                var bookedStr = row["Number of Booked Apartment"]?.ToString()
                             ?? row["Number of Booked Apartments"]?.ToString();
                var areaStr = row["Saleable Area (in Sqmts)"]?.ToString()
                           ?? row["Saleable Area (In Sqmts)"]?.ToString();

                int.TryParse(unitsStr, out var units);
                int.TryParse(bookedStr, out var booked);
                double.TryParse(areaStr, System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var area);

                totalFlats += units;
                totalBooked += booked;
                totalSaleableArea += area * units;
            }

            if (totalFlats > 0)
            {
                project["totalFlats"]            = totalFlats;
                project["totalBookedFlats"]       = totalBooked;
                project["totalSaleableAreaSqmt"]  = Math.Round(totalSaleableArea, 2);
                project["avgUnitSizeSqmt"]        = Math.Round(totalSaleableArea / totalFlats, 2);
                project["avgUnitSizeSqft"]        = Math.Round(totalSaleableArea / totalFlats * 10.7639, 1);
                project["bookingPercent"]         = Math.Round((double)totalBooked / totalFlats * 100, 1);
                return;
            }

            // Fallback: some projects (e.g. Prestige Beverly Hills) embed floor data as a blob
            // inside Building Tower Details row[N]["Name"] instead of a proper Floor Breakdown table.
            // Pattern in blob: <sr> <floorId> <True|False> <aptType> <area> <numApt> <numBooked>
            var towerDetails = data["Building Tower Details"] as JArray;
            if (towerDetails == null) return;
            var blobPattern = new System.Text.RegularExpressions.Regex(
                @"\d+\s+\d+\s+(?:True|False)\s+\S+\s+[\d.]+\s+(\d+)\s+(\d+)");
            foreach (var tRow in towerDetails)
            {
                var name = tRow["Name"]?.ToString() ?? "";
                if (name.Length < 200) continue; // only blob rows are very long
                foreach (System.Text.RegularExpressions.Match m in blobPattern.Matches(name))
                {
                    int.TryParse(m.Groups[1].Value, out var units);
                    int.TryParse(m.Groups[2].Value, out var booked);
                    totalFlats  += units;
                    totalBooked += booked;
                }
            }
            if (totalFlats > 0)
            {
                project["totalFlats"]      = totalFlats;
                project["totalBookedFlats"] = totalBooked;
            }
        }

        /// <summary>
        /// Extracts shortlisted fields from nested JSON structure
        /// Maps to frontend-compatible camelCase keys
        /// </summary>
        private Dictionary<string, object> ExtractFields(JObject data)
        {
            var result = new Dictionary<string, object>();

            void Flatten(JObject obj)
            {
                foreach (var property in obj.Properties())
                {
                    if (property.Value is JObject nestedObj)
                    {
                        Flatten(nestedObj);
                    }
                    else if (_shortlistedFields.Contains(property.Name))
                    {
                        result[property.Name] = property.Value.ToString();
                    }
                }
            }

            Flatten(data);
            
            // Map to frontend-compatible keys for RERA Compliance calculation
            MapFrontendFields(result);
            
            return result;
        }
        
        /// <summary>
        /// Maps backend field names to frontend camelCase equivalents
        /// Ensures all frontend components (RERA Compliance, Comparison, Properties List, etc.) work correctly
        /// </summary>
        private void MapFrontendFields(Dictionary<string, object> result)
        {
            // PROJECT BASIC INFO
            if (result.TryGetValue("Project Name", out var projectName))
            {
                result["projectName"] = projectName;
            }
            
            if (result.TryGetValue("Project Status", out var status))
            {
                result["projectStatus"] = status;
            }
            
            if (result.TryGetValue("Project Type", out var projectType))
            {
                result["projectType"] = projectType;
            }
            
            // DEVELOPER/PROMOTER INFO
            if (result.TryGetValue("Name", out var developerName))
            {
                result["promoterName"] = developerName;
                result["developerName"] = developerName;
            }
            
            // LOCATION FIELDS
            if (result.TryGetValue("District", out var districtVal))
            {
                result["district"] = districtVal;
            }
            
            if (result.TryGetValue("Locality", out var locality))
            {
                result["locality"] = locality;
            }
            
            if (result.TryGetValue("Pin Code", out var pinCode))
            {
                result["pinCode"] = pinCode;
            }
            
            if (result.TryGetValue("Mandal", out var mandal))
            {
                result["mandal"] = mandal;
            }
            
            if (result.TryGetValue("Village/City/Town", out var city))
            {
                result["city"] = city;
            }
            
            // AREA FIELDS
            if (result.TryGetValue("Total Area(In sqmts)", out var totalArea))
            {
                result["plotArea"] = totalArea;
                result["totalArea"] = totalArea;
            }
            
            if (result.TryGetValue("Net Area(In sqmts)", out var netArea))
            {
                result["netArea"] = netArea;
            }
            
            if (result.TryGetValue("Approved Built up Area (In Sqmts)", out var approvedArea))
            {
                result["approvedPlotArea"] = approvedArea;
                result["approvedBuildUpArea"] = approvedArea;
            }
            
            if (result.TryGetValue("Mortgage Area (In Sqmts)", out var mortgageArea))
            {
                result["mortgageArea"] = mortgageArea;
            }
            
            // DATES & RERA COMPLIANCE FIELDS
            if (result.TryGetValue("Approved Date", out var approvedDate))
            {
                result["dateOfRegistration"] = approvedDate;
                result["registrationDate"] = approvedDate;
                result["approvedDate"] = approvedDate;
            }
            
            if (result.TryGetValue("Proposed Date of Completion", out var completionDate))
            {
                result["proposedDateOfCompletion"] = completionDate;
            }
            
            if (result.TryGetValue("Revised Proposed Date of Completion", out var revisedDate))
            {
                result["revisedDateOfCompletion"] = revisedDate;
            }
            
            // PLAN APPROVAL
            if (result.TryGetValue("Plan Approval Number", out var planNumber))
            {
                result["approvalOfPlan"] = planNumber;
                result["planApprovalNumber"] = planNumber;
            }
            else if (result.TryGetValue("Project Type", out var pType))
            {
                result["approvalOfPlan"] = $"Approved - {pType}";
            }
            
            // GENERATE RERA REGISTRATION NUMBER
            var regNumber = "";
            if (result.TryGetValue("Approved Date", out var regDate))
            {
                var datePart = regDate.ToString()?.Replace("/", "");
                var district = result.TryGetValue("District", out var dist) ? dist.ToString() : "HYD";
                var districtCode = GetDistrictCode(district?.ToString() ?? "");
                regNumber = $"P{districtCode}{datePart}";
                result["registrationNumber"] = regNumber;
            }
            
            // PROJECT ID (for comparison component)
            if (result.TryGetValue("id", out var id))
            {
                result["projectId"] = id;
            }
            
            // BANK DETAILS
            if (result.TryGetValue("Bank Name", out var bankName))
            {
                result["bankName"] = bankName;
            }
            
            if (result.TryGetValue("Branch Name", out var branchName))
            {
                result["branchName"] = branchName;
            }
            
            // ORGANIZATION INFO
            if (result.TryGetValue("Organization Type", out var orgType))
            {
                result["organizationType"] = orgType;
            }
            
            // SURVEY NUMBERS
            if (result.TryGetValue("Sy.No/TS No.", out var surveyNo))
            {
                result["surveyNumber"] = surveyNo;
            }
            
            // REVIEWS & RATINGS (Default values - can be updated from actual review data)
            result["averageRating"] = 0.0; // Will be calculated from actual reviews
            result["reviewCount"] = 0;
            result["totalReviews"] = 0;
            
            // COMPLIANCE FLAGS
            result["isReraApproved"] = !string.IsNullOrEmpty(regNumber);
            result["hasLitigation"] = result.TryGetValue("Litigations related to the project ?", out var lit) 
                && lit.ToString()?.ToLower() == "yes";
            
            // BUILDING DETAILS (if available)
            if (result.TryGetValue("Total Building Units (as per approved plan)", out var buildingUnits))
            {
                result["proposedNoOfBuildings"] = buildingUnits;
                result["totalBuildings"] = buildingUnits;
            }
            
            // Set defaults for fields that might not exist
            if (!result.ContainsKey("proposedNoOfFloors"))
            {
                result["proposedNoOfFloors"] = "N/A";
            }

            // OCCUPANCY DENSITY CALCULATION
            result["occupancyDensity"] = CalculateOccupancyDensity(result);
        }

        /// <summary>
        /// Calculates occupancy density metrics using FAR (Floor Area Ratio) and unit density.
        /// FAR = Approved Built-up Area / Net Area (all floors combined vs land).
        /// Lower FAR = more open space, less crowded.
        /// Thresholds adjust based on project type (villa vs apartment vs high-rise).
        /// </summary>
        private Dictionary<string, object> CalculateOccupancyDensity(Dictionary<string, object> data)
        {
            var density = new Dictionary<string, object>();

            // Parse area values (sqmts)
            double netArea = 0, totalArea = 0, builtUpArea = 0;
            double.TryParse(data.TryGetValue("Net Area(In sqmts)", out var na) ? na?.ToString() : null, out netArea);
            double.TryParse(data.TryGetValue("Total Area(In sqmts)", out var ta) ? ta?.ToString() : null, out totalArea);
            double.TryParse(data.TryGetValue("Approved Built up Area (In Sqmts)", out var bua) ? bua?.ToString() : null, out builtUpArea);

            // Prefer net area; fall back to total area
            double landArea = netArea > 0 ? netArea : totalArea;

            // ── Flat count ─────────────────────────────────────────────────────────────
            // Prefer the real flat count derived from Floor Breakdown rows (set by ExtractFloorBreakdownStats).
            // "Total Building Units" in RERA data = number of towers, NOT individual flats — don't use it for density.
            double units = 0;
            if (data.TryGetValue("totalFlats", out var tfObj) &&
                double.TryParse(tfObj?.ToString(), out var flatCount) && flatCount > 0)
            {
                units = flatCount;
            }
            // No reliable flat-count fallback from other scalar fields; units stays 0 → fallback FAR path below.

            var projectTypeRaw = data.TryGetValue("Project Type", out var pt) ? pt?.ToString()?.ToLower() ?? "" : "";
            var isMsbRaw = data.TryGetValue("Is the project an MSB or a High-Rise?", out var msbVal)
                ? msbVal?.ToString()?.ToLower() ?? "" : "";
            bool isMsb       = isMsbRaw == "yes";
            bool isPlot      = projectTypeRaw.Contains("plot") || projectTypeRaw.Contains("layout");
            bool isVilla     = !isMsb && (projectTypeRaw.Contains("villa") || projectTypeRaw.Contains("row"));
            bool isApartment = isMsb || projectTypeRaw.Contains("apartment") || projectTypeRaw.Contains("flat") || projectTypeRaw.Contains("residential");
            bool isCommercial = projectTypeRaw.Contains("commercial") || projectTypeRaw.Contains("office") || projectTypeRaw.Contains("retail");
            bool isMixed     = projectTypeRaw.Contains("mixed");

            density["landAreaSqmt"]    = Math.Round(landArea, 2);
            density["builtUpAreaSqmt"] = Math.Round(builtUpArea, 2);
            density["totalFlats"]      = (int)units;  // real flat count from Floor Breakdown (0 if unavailable)
            density["projectTypeRaw"]  = data.TryGetValue("Project Type", out var ptOrig) ? ptOrig?.ToString() ?? "" : "";

            // Expose avg unit size & booking % if derived from Floor Breakdown
            if (data.TryGetValue("avgUnitSizeSqmt", out var avgSqmt))  density["avgUnitSizeSqmt"] = avgSqmt;
            if (data.TryGetValue("avgUnitSizeSqft", out var avgSqft))  density["avgUnitSizeSqft"] = avgSqft;
            if (data.TryGetValue("bookingPercent",   out var bkPct))   density["bookingPercent"]   = bkPct;
            if (data.TryGetValue("totalBookedFlats", out var bkFlats)) density["totalBookedFlats"] = bkFlats;
            if (data.TryGetValue("totalSaleableAreaSqmt", out var tsa)) density["totalSaleableAreaSqmt"] = tsa;

            if (landArea <= 0)
            {
                density["available"] = false;
                density["reason"]    = "Insufficient area data";
                return density;
            }

            density["available"] = true;

            // ── 1. FAR (Floor Area Ratio) ──────────────────────────────────────
            // FAR > 1 means built-up area across all floors exceeds land size
            double far = builtUpArea > 0 ? Math.Round(builtUpArea / landArea, 2) : 0;
            density["far"] = far;
            density["farLabel"] = far > 0 ? $"{far:F2}x" : "N/A";

            // ── 2. Unit Density (units per hectare = units × 10000 / sqmts) ────
            double unitsPerHectare = units > 0 ? Math.Round(units * 10000.0 / landArea, 1) : 0;
            density["unitsPerHectare"] = unitsPerHectare;

            // ── 3. Open Space Ratio ──────────────────────────────────────────────
            // For high-rise buildings the ground footprint is small (35-40% coverage).
            // For mid-rise 50-55%, for low-rise/villa 60-70%.
            // FAR tells us how tall the building effectively is, so we infer coverage:
            double groundCoverageRatio = far <= 0.5 ? 0.65 : far <= 1.5 ? 0.55 : far <= 3.0 ? 0.40 : 0.30;
            double groundFootprint = builtUpArea > 0 ? landArea * groundCoverageRatio : 0;
            double openSpaceRatio = groundFootprint > 0 && landArea > 0
                ? Math.Max(0, Math.Round((landArea - groundFootprint) / landArea * 100, 1))
                : 0;
            density["openSpacePercent"] = openSpaceRatio;

            // ── 4. Category & Label ───────────────────────────────────────────────
            // Thresholds differ by project type because a FAR of 0.5 is normal for
            // villa layouts but dense for a standalone plot development.
            string category, label, interpretation, color, icon;
            int score; // 0 = extremely dense, 100 = very open

            if (isPlot)
            {
                // Plot layouts: measure unit density (plots/ha), FAR rarely applies
                if      (unitsPerHectare <= 15)  { category = "Very Low";  score = 95; color = "#16a34a"; icon = "🌿"; label = "Open Plot Layout";          interpretation = "Spacious individual plots — maximum privacy and open land per plot."; }
                else if (unitsPerHectare <= 30)  { category = "Low";       score = 75; color = "#65a30d"; icon = "🏡"; label = "Standard Plot Community";    interpretation = "Comfortable spacing between plots. Good for independent villas."; }
                else if (unitsPerHectare <= 60)  { category = "Medium";    score = 50; color = "#d97706"; icon = "🏘️"; label = "Compact Plot Layout";        interpretation = "Moderately dense layout. Shared open spaces likely."; }
                else                              { category = "High";      score = 25; color = "#dc2626"; icon = "🔴"; label = "Dense Plot Subdivision";     interpretation = "High plot count per area. Less individual open space."; }
            }
            else if (isVilla || (far > 0 && far < 0.8 && !isCommercial))
            {
                // Villas / row houses / independent
                if      (far <= 0.3)             { category = "Very Low";  score = 95; color = "#16a34a"; icon = "🌳"; label = "Ultra-Low Density Villas";    interpretation = "Large grounds per villa. Exceptional open space and privacy."; }
                else if (far <= 0.5)             { category = "Low";       score = 80; color = "#65a30d"; icon = "🏡"; label = "Gated Villa Community";        interpretation = "Good space per unit. Private garden likely per villa."; }
                else if (far <= 0.8)             { category = "Medium";    score = 60; color = "#d97706"; icon = "🏘️"; label = "Row House / Compact Villa";    interpretation = "Moderate density. Shared amenity spaces with limited private yards."; }
                else                              { category = "High";      score = 35; color = "#ea580c"; icon = "🏗️"; label = "High-Density Low-Rise";       interpretation = "Dense low-rise. Mostly shared spaces with minimal open land."; }
            }
            else if (isCommercial || isMixed)
            {
                // Commercial / mixed-use: higher FAR is expected
                if      (far <= 1.5)             { category = "Low";       score = 75; color = "#65a30d"; icon = "🏢"; label = "Low-Rise Commercial";          interpretation = "Low commercial density. Good parking and setback area."; }
                else if (far <= 3.0)             { category = "Medium";    score = 55; color = "#d97706"; icon = "🏬"; label = "Mid-Rise Mixed Use";            interpretation = "Typical urban commercial density."; }
                else if (far <= 5.0)             { category = "High";      score = 35; color = "#ea580c"; icon = "🏙️"; label = "High-Rise Commercial";         interpretation = "High commercial FAR. Dense urban core development."; }
                else                              { category = "Very High"; score = 15; color = "#dc2626"; icon = "🔴"; label = "Skyscraper / CBD Density";     interpretation = "Extremely high density. Central business district profile."; }
            }
            else
            {
                // Residential apartments / high-rise — most common case.
                // We use units/hectare, NOT FAR, because high-rise towers naturally have high FAR
                // (many floors × floor area > land area) but that doesn't mean poor quality for residents.
                // What actually matters is: how many families share each hectare of land?
                // A 30-floor tower with 300 units on 2 acres can have MORE ground-level open
                // space per family than a 4-floor building with 150 units on the same 2 acres.
                if (unitsPerHectare <= 0)
                {
                    // No unit count in RERA data — fall back to informational FAR-based label
                    if      (far <= 1.5) { category = "Low";       score = 70; color = "#65a30d"; icon = "🏡"; label = "Low-Rise Apartments";    interpretation = "Low FAR. Likely 4–6 floors with good common space."; }
                    else if (far <= 3.0) { category = "Medium";    score = 50; color = "#d97706"; icon = "🏘️"; label = "Mid-Rise Residential";   interpretation = "Typical urban apartment. FAR is informational — floor count naturally drives this up."; }
                    else                 { category = "High";      score = 30; color = "#ea580c"; icon = "🏗️"; label = "High-Rise Complex";       interpretation = "High FAR typical of 15+ storey towers. Open space depends on building footprint."; }
                }
                else if (unitsPerHectare <= 100)  { category = "Very Low";  score = 92; color = "#16a34a"; icon = "🌿"; label = "Spacious Residential Estate";  interpretation = "Very few families per hectare — luxury-level open space and gardens per unit."; }
                else if (unitsPerHectare <= 250)  { category = "Low";       score = 75; color = "#65a30d"; icon = "🏡"; label = "Comfortable Gated Community";   interpretation = "Good residential density. Ample space for clubhouse, parks and amenities."; }
                else if (unitsPerHectare <= 450)  { category = "Medium";    score = 52; color = "#d97706"; icon = "🏘️"; label = "Typical Urban Apartment";       interpretation = "Standard Hyderabad apartment density. Shared amenities, reasonable open areas."; }
                else if (unitsPerHectare <= 700)  { category = "High";      score = 30; color = "#ea580c"; icon = "🏗️"; label = "Dense Tower Complex";           interpretation = "High residential density. Amenities are heavily shared across many families."; }
                else                              { category = "Very High"; score = 12; color = "#dc2626"; icon = "🏙️"; label = "Ultra-Dense Development";       interpretation = "Extremely dense. Very limited open/green space per family."; }
            }

            density["category"]       = category;
            density["label"]          = label;
            density["interpretation"] = interpretation;
            density["score"]          = score;
            density["color"]          = color;
            density["icon"]           = icon;

            // ── 5. Land area in human-readable units ────────────────────────────
            density["landAreaAcres"] = Math.Round(landArea / 4046.86, 2);
            density["landAreaHa"]    = Math.Round(landArea / 10000.0, 3);

            return density;
        }
        
        /// <summary>
        /// Gets district code for RERA registration number
        /// </summary>
        private string GetDistrictCode(string district)
        {
            var districtLower = district.ToLowerInvariant();
            
            if (districtLower.Contains("hyderabad")) return "02051";
            if (districtLower.Contains("ranga") || districtLower.Contains("reddy")) return "02052";
            if (districtLower.Contains("sangareddy")) return "02053";
            if (districtLower.Contains("medchal")) return "02054";
            
            return "02050"; // Default Telangana code
        }

        #endregion

        // ── Admin CRUD — file-based repo delegates to PostgreSQL for write ops ──
        // These return NotSupportedException because writes go to the Postgres repo.
        public Task<bool> UpdateProjectAsync(string projectId, Dictionary<string, object> updates)
            => throw new NotSupportedException("UpdateProject is only supported with PostgreSQL repository.");

        public Task<bool> DeleteProjectAsync(string projectId)
            => throw new NotSupportedException("DeleteProject is only supported with PostgreSQL repository.");

        public Task<string> CreateProjectAsync(Dictionary<string, object> projectData)
            => throw new NotSupportedException("CreateProject is only supported with PostgreSQL repository.");
    }
}
