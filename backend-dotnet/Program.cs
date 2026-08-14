using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using HyderabadUrbanReality.Application.Services;
using HyderabadUrbanReality.Infrastructure.Services;
using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using System.Text;
using AspNetCoreRateLimit;

// ── Force Npgsql to treat all DateTime as UTC ─────────────────────────────────
// Without this, DateTime.UtcNow values get stored as the server's local time.
// Postgres timezone is Asia/Calcutta (+05:30) which causes tokens to appear
// expired the moment they are inserted.
AppContext.SetSwitch("Npgsql.EnableLegacyTimestampBehavior", false);

// ── Suppress inotify/FileSystemWatcher before ASP.NET Core initialises config ─
// Render free tier has a system-wide inotify limit of 128. ASP.NET Core's default
// configuration pipeline sets up FileSystemWatcher on every appsettings*.json file
// inside ConfigurationManager.AddSource — before any app code runs — which exhausts
// the limit and crashes the process. Setting this env var disables all file watchers
// at the dotnet runtime level before the builder touches the config system.
Environment.SetEnvironmentVariable("DOTNET_USE_POLLING_FILE_WATCHER", "true");
// Alternatively, disable entirely — polling still won't help on Render, but the
// real fix is telling the config sources not to watch at all via the host option below.
// We set both to be safe.
Environment.SetEnvironmentVariable("DOTNET_hostBuilder__reloadConfigOnChange", "false");

var builder = WebApplication.CreateBuilder(new WebApplicationOptions
{
    Args = args,
    // Suppress the default appsettings reload-on-change watcher
    EnvironmentName = Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ?? "Production"
});

// Belt-and-suspenders: also turn off ReloadOnChange on any file source added later
builder.Configuration.Sources
    .OfType<Microsoft.Extensions.Configuration.FileConfigurationSource>()
    .ToList()
    .ForEach(s => s.ReloadOnChange = false);

// ── Disable config file watching in production (avoids inotify limit on Render free tier) ──
if (!builder.Environment.IsDevelopment())
{
    builder.Host.ConfigureAppConfiguration((ctx, config) =>
    {
        foreach (var source in config.Sources.OfType<Microsoft.Extensions.Configuration.FileConfigurationSource>())
            source.ReloadOnChange = false;
    });
}
// ── Load .env file for local secrets (not committed to source control) ────────
var envFile = Path.Combine(Directory.GetCurrentDirectory(), ".env");
if (File.Exists(envFile))
{
    foreach (var line in File.ReadAllLines(envFile))
    {
        var trimmed = line.Trim();
        if (string.IsNullOrEmpty(trimmed) || trimmed.StartsWith('#')) continue;
        var eq = trimmed.IndexOf('=');
        if (eq < 0) continue;
        var envKey   = trimmed[..eq].Trim();
        var envValue = trimmed[(eq + 1)..].Trim();
        // ASP.NET Core config uses __ as section separator in env vars
        Environment.SetEnvironmentVariable(envKey, envValue);
    }
}
// ── Reload config so env vars override appsettings.json
builder.Configuration.AddEnvironmentVariables();

// ── Startup diagnostic: log connection string presence (not the value) ────────
var connStr = builder.Configuration.GetConnectionString("DefaultConnection");
Console.WriteLine(string.IsNullOrWhiteSpace(connStr)
    ? "STARTUP ERROR: ConnectionStrings__DefaultConnection is NOT set — database will be unavailable."
    : $"STARTUP OK: ConnectionStrings__DefaultConnection is set (length={connStr.Length}, host={connStr.Split(';').FirstOrDefault(s => s.TrimStart().StartsWith("Host", StringComparison.OrdinalIgnoreCase)) ?? connStr.Split('@').LastOrDefault()?.Split('/').FirstOrDefault() ?? "unknown"})");

// ── Test DB connectivity at startup + keepalive ping every 4 minutes ─────────
// Render free tier spins down after 15 min inactivity. The keepalive prevents
// the Npgsql connection pool from holding stale sockets that time out on first use.
if (!string.IsNullOrWhiteSpace(connStr))
{
    _ = Task.Run(async () =>
    {
        try
        {
            await Task.Delay(3000); // wait for app to fully start
            await using var testConn = new Npgsql.NpgsqlConnection(connStr);
            await testConn.OpenAsync();
            await using var cmd = testConn.CreateCommand();
            cmd.CommandText = "SELECT COUNT(*) FROM projects";
            var count = await cmd.ExecuteScalarAsync();
            Console.WriteLine($"DB CONNECT OK: projects table has {count} rows");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"DB CONNECT FAIL: {ex.GetType().Name}: {ex.Message}");
            if (ex.InnerException != null)
                Console.WriteLine($"DB CONNECT INNER: {ex.InnerException.Message}");
        }
    });

    // Keepalive: ping DB every 4 minutes to prevent idle connection timeouts
    _ = Task.Run(async () =>
    {
        await Task.Delay(TimeSpan.FromMinutes(1)); // initial delay
        while (true)
        {
            try
            {
                await using var pingConn = new Npgsql.NpgsqlConnection(connStr);
                await pingConn.OpenAsync();
                await using var pingCmd = pingConn.CreateCommand();
                pingCmd.CommandText = "SELECT 1";
                await pingCmd.ExecuteScalarAsync();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"DB KEEPALIVE FAIL: {ex.Message}");
                Npgsql.NpgsqlConnection.ClearAllPools();
            }
            await Task.Delay(TimeSpan.FromMinutes(4));
        }
    });
}

// ── Configure Dapper to map snake_case columns to PascalCase C# properties ──
Dapper.DefaultTypeMap.MatchNamesWithUnderscores = true;

// ── Dapper does not support DateOnly natively; register a type handler ────────
Dapper.SqlMapper.AddTypeHandler(new DateOnlyTypeHandler());

// ── Configure Npgsql to treat all timestamps as UTC ──────────────────────────
AppContext.SetSwitch("Npgsql.EnableLegacyTimestampBehavior", true);

// Add services to the container
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // Case-insensitive property matching so { "password": "..." } maps to Password, etc.
        options.JsonSerializerOptions.PropertyNameCaseInsensitive = true;
        options.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    });
builder.Services.AddEndpointsApiExplorer();

// Configure settings from appsettings.json
// Follows Dependency Inversion Principle - inject configuration
builder.Services.Configure<AppSettings>(builder.Configuration.GetSection("AppSettings"));
builder.Services.Configure<ReraSettings>(builder.Configuration.GetSection("ReraSettings"));
builder.Services.Configure<OpenStreetMapSettings>(builder.Configuration.GetSection("OpenStreetMapSettings"));
builder.Services.Configure<SeleniumSettings>(builder.Configuration.GetSection("SeleniumSettings"));

// Get allowed origins from configuration
var appSettings = builder.Configuration.GetSection("AppSettings").Get<AppSettings>();
var allowedOrigins = appSettings?.AllowedOrigins?.Split(',', StringSplitOptions.RemoveEmptyEntries) 
    ?? new[] { "http://localhost:4200" };

// Add CORS with restricted origins
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowSpecificOrigins", policy =>
    {
        policy.WithOrigins(allowedOrigins)
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials();
    });
});

// Add JWT Authentication
var jwtSecret = appSettings?.JwtSecret ?? throw new InvalidOperationException("JWT Secret not configured");
var key = Encoding.ASCII.GetBytes(jwtSecret);

builder.Services.AddAuthentication(x =>
{
    x.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    x.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(x =>
{
    x.RequireHttpsMetadata = !builder.Environment.IsDevelopment();
    x.SaveToken = true;
    x.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = new SymmetricSecurityKey(key),
        ValidateIssuer = false,
        ValidateAudience = false,
        ClockSkew = TimeSpan.Zero
    };
});

builder.Services.AddAuthorization();

// Add session support with secure cookies
builder.Services.AddDistributedMemoryCache();
builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromMinutes(30);
    options.Cookie.Name = "__Host-Session";
    options.Cookie.HttpOnly = true;
    options.Cookie.SecurePolicy = builder.Environment.IsDevelopment() 
        ? CookieSecurePolicy.SameAsRequest 
        : CookieSecurePolicy.Always;
    options.Cookie.SameSite = SameSiteMode.Strict;
    options.Cookie.IsEssential = true;
});

// Add rate limiting — IMemoryCache also used by ProjectService for project data caching
builder.Services.AddMemoryCache();
builder.Services.Configure<IpRateLimitOptions>(builder.Configuration.GetSection("IpRateLimiting"));
builder.Services.AddInMemoryRateLimiting();
builder.Services.AddSingleton<IRateLimitConfiguration, RateLimitConfiguration>();

// Register repositories (Data Access Layer)
// Follows Repository Pattern
// Feature flag: UsePostgresRepository toggles between file-based and PostgreSQL repository (Req 3.1–3.3)
var usePostgres = builder.Configuration.GetValue<bool>("FeatureFlags:UsePostgresRepository");
if (usePostgres)
{
    builder.Services.AddScoped<IProjectRepository, HyderabadUrbanReality.Infrastructure.Repositories.PostgresProjectRepository>();
}
else
{
    builder.Services.AddScoped<IProjectRepository, HyderabadUrbanReality.Infrastructure.Repositories.ProjectRepository>();
}

// Register user repositories
builder.Services.AddScoped<HyderabadUrbanReality.Core.Interfaces.IUserRepository, HyderabadUrbanReality.Infrastructure.Repositories.UserRepository>();
builder.Services.AddScoped<HyderabadUrbanReality.Core.Interfaces.IUserDataRepository, HyderabadUrbanReality.Infrastructure.Repositories.UserDataRepository>();
builder.Services.AddScoped<HyderabadUrbanReality.Infrastructure.Repositories.LeadRepository>();
builder.Services.AddScoped<HyderabadUrbanReality.Infrastructure.Repositories.MediaRepository>();
builder.Services.AddScoped<HyderabadUrbanReality.Infrastructure.Repositories.ReviewRepository>();
builder.Services.AddScoped<HyderabadUrbanReality.Infrastructure.Repositories.ScheduleVisitRepository>();

// Register email service — uses Resend HTTP API (SMTP is blocked on Render free tier)
builder.Services.AddScoped<HyderabadUrbanReality.Core.Interfaces.IEmailService, HyderabadUrbanReality.Infrastructure.Services.ResendEmailService>();

// Register application services (Business Logic Layer)
// Follows Dependency Inversion - register interfaces
builder.Services.AddScoped<IProjectService, HyderabadUrbanReality.Application.Services.ProjectService>();
builder.Services.AddScoped<IAuthenticationService, AuthenticationService>();
builder.Services.AddScoped<IFileService, FileService>();
builder.Services.AddScoped<IInputSanitizer, InputSanitizer>();

// Register infrastructure services (External Dependencies)
builder.Services.AddSingleton<IOpenStreetMapService, OpenStreetMapService>();

// Register Python scraper client with HttpClient factory
builder.Services.AddHttpClient();
builder.Services.AddHttpClient("twitter-oembed", c =>
{
    c.DefaultRequestHeaders.Add("User-Agent", "HydUrban/1.0");
    c.Timeout = TimeSpan.FromSeconds(10);
});
builder.Services.AddScoped<IPythonScraperClient, PythonScraperClientService>();

var app = builder.Build();

// Configure the HTTP request pipeline
if (app.Environment.IsDevelopment())
{
    // Swagger removed — incompatible with .NET 10; use /api/* endpoints directly
}
else
{
    // Render handles TLS termination at the edge — no internal HTTPS needed.
    // app.UseHttpsRedirection() would cause redirect loops behind Render's proxy.
    app.UseHsts();
}

// Add security headers
app.Use(async (context, next) =>
{
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    context.Response.Headers["X-Frame-Options"] = "DENY";
    context.Response.Headers["X-XSS-Protection"] = "1; mode=block";
    context.Response.Headers["Referrer-Policy"] = "no-referrer";
    context.Response.Headers["Content-Security-Policy"] =
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;";
    
    await next();
});

// Apply rate limiting
app.UseIpRateLimiting();

// Apply CORS
app.UseCors("AllowSpecificOrigins");

app.UseSession();
app.UseAuthentication();

// Deactivated-user guard: return 401 for is_active=false users (Req 12.7)
app.Use(async (context, next) =>
{
    if (context.User.Identity?.IsAuthenticated == true)
    {
        var subClaim = context.User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value
                    ?? context.User.FindFirst("sub")?.Value;
        if (subClaim is not null && Guid.TryParse(subClaim, out var userId))
        {
            var userRepo = context.RequestServices
                .GetService<HyderabadUrbanReality.Core.Interfaces.IUserRepository>();
            if (userRepo is not null)
            {
                var user = await userRepo.GetByIdAsync(userId);
                if (user is not null && !user.IsActive)
                {
                    context.Response.StatusCode = 401;
                    await context.Response.WriteAsJsonAsync(new { error = "account_deactivated" });
                    return;
                }
            }
        }
    }
    await next();
});

app.UseAuthorization();
app.MapControllers();

// Serve uploaded property media files
var uploadFolder = Path.Combine(Directory.GetCurrentDirectory(), "uploads");
if (!Directory.Exists(uploadFolder)) Directory.CreateDirectory(uploadFolder);
app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new Microsoft.Extensions.FileProviders.PhysicalFileProvider(uploadFolder),
    RequestPath  = "/media"
});

// ── Bind to 0.0.0.0 for Render / cloud hosting ──────────────────────────────
// ASPNETCORE_URLS env var takes priority; this is the explicit fallback.
var port = Environment.GetEnvironmentVariable("PORT") ?? "5001";
app.Urls.Add($"http://0.0.0.0:{port}");

app.Run();

// ── DateOnly ↔ Dapper bridge ────────────────────────────────────────────────
// Must be outside top-level statements (CS8803). Converts DateOnly to/from
// DateTime for SQL parameter binding since Dapper has no built-in handler.
sealed file class DateOnlyTypeHandler : Dapper.SqlMapper.TypeHandler<DateOnly>
{
    public override void SetValue(System.Data.IDbDataParameter parameter, DateOnly value)
        => parameter.Value = value.ToDateTime(TimeOnly.MinValue);

    public override DateOnly Parse(object value)
        => DateOnly.FromDateTime(Convert.ToDateTime(value));
}
