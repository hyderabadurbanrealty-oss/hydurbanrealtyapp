using HyderabadUrbanReality.Core.Interfaces;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Email service using Resend HTTP API (https://resend.com).
    /// Replaces MailKit SMTP which is blocked on Render free tier.
    /// Config keys:
    ///   ResendSettings:ApiKey      — Resend API key (re_xxxx...)
    ///   ResendSettings:FromEmail   — verified sender e.g. noreply@hyderabadurbanrealty.com
    ///   ResendSettings:FromName    — display name
    ///   ResendSettings:AdminEmail  — admin notification target
    ///   SmtpSettings:AppBaseUrl    — base URL for email links (reused from existing config)
    /// </summary>
    public class ResendEmailService : IEmailService
    {
        private readonly IConfiguration _config;
        private readonly IHttpClientFactory _http;
        private readonly ILogger<ResendEmailService> _logger;

        public ResendEmailService(
            IConfiguration config,
            IHttpClientFactory http,
            ILogger<ResendEmailService> logger)
        {
            _config = config;
            _http   = http;
            _logger = logger;
        }

        public async Task SendVerificationEmailAsync(string toEmail, string fullName, string rawToken)
        {
            var baseUrl = BaseUrl();
            var link    = $"{baseUrl}/verify-email?token={Uri.EscapeDataString(rawToken)}";
            var subject = "Verify your Hyderabad Urban Realty account";
            var body    = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;background:#f7f8fa;padding:32px 16px;"">
  <div style=""background:linear-gradient(135deg,#0d1f3c,#0d3b73);border-radius:10px 10px 0 0;padding:28px 32px;"">
    <span style=""color:white;font-size:20px;font-weight:700;"">Hyderabad Urban Realty</span>
  </div>
  <div style=""background:#ffffff;border:1px solid #e8ecf2;border-top:none;border-radius:0 0 10px 10px;padding:32px;"">
    <h2 style=""color:#0d1f3c;font-size:20px;margin:0 0 12px;"">Verify your email address</h2>
    <p style=""color:#374151;font-size:14px;line-height:1.6;margin:0 0 24px;"">
      Hi {HtmlEncode(fullName)},<br><br>
      Thank you for registering. Click the button below to verify your email address.
      This link is valid for <strong>24 hours</strong>.
    </p>
    <a href=""{link}"" style=""display:inline-block;background:#0d3b73;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 28px;border-radius:7px;"">
      Verify Email Address
    </a>
    <p style=""color:#94a3b8;font-size:12px;margin:24px 0 0;"">
      If you did not create an account, ignore this email.<br>
      Or copy: <a href=""{link}"" style=""color:#0d3b73;word-break:break-all;"">{link}</a>
    </p>
  </div>
</div>";
            await SendAsync(toEmail, fullName, subject, body);
        }

        public async Task SendPasswordResetEmailAsync(string toEmail, string fullName, string rawToken)
        {
            var baseUrl = BaseUrl();
            var link    = $"{baseUrl}/reset-password?token={Uri.EscapeDataString(rawToken)}";
            var subject = "Reset your HydUrban password";
            var body    = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;background:#f7f8fa;padding:32px 16px;"">
  <div style=""background:linear-gradient(135deg,#0d1f3c,#0d3b73);border-radius:10px 10px 0 0;padding:28px 32px;"">
    <span style=""color:white;font-size:20px;font-weight:700;"">Hyderabad Urban Realty</span>
  </div>
  <div style=""background:#ffffff;border:1px solid #e8ecf2;border-top:none;border-radius:0 0 10px 10px;padding:32px;"">
    <h2 style=""color:#0d1f3c;font-size:20px;margin:0 0 12px;"">Reset your password</h2>
    <p style=""color:#374151;font-size:14px;line-height:1.6;margin:0 0 24px;"">
      Hi {HtmlEncode(fullName)},<br><br>
      We received a request to reset your password. This link is valid for <strong>1 hour</strong>.
    </p>
    <a href=""{link}"" style=""display:inline-block;background:#0d3b73;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 28px;border-radius:7px;"">
      Reset Password
    </a>
    <p style=""color:#94a3b8;font-size:12px;margin:24px 0 0;"">
      If you did not request this, ignore this email.<br>
      Or copy: <a href=""{link}"" style=""color:#0d3b73;word-break:break-all;"">{link}</a>
    </p>
  </div>
</div>";
            await SendAsync(toEmail, fullName, subject, body);
        }

        public async Task SendReviewNotificationAsync(string projectName, string reviewerName,
            string reviewerEmail, int rating, string reviewText)
        {
            var adminEmail = AdminEmail();
            if (string.IsNullOrEmpty(adminEmail)) return;
            var stars   = new string('★', rating) + new string('☆', 5 - rating);
            var subject = $"New Review: {HtmlEncode(projectName)} — {rating}/5 stars";
            var body    = $@"<h2>New Review: {HtmlEncode(projectName)}</h2>
<p><strong>Reviewer:</strong> {HtmlEncode(reviewerName)} &lt;{HtmlEncode(reviewerEmail)}&gt;</p>
<p><strong>Rating:</strong> {stars}</p>
<p><strong>Review:</strong> {HtmlEncode(reviewText)}</p>
<p>Log in to admin panel to approve or reject.</p>";
            await SendAsync(adminEmail, "HydUrban Admin", subject, body);
        }

        public async Task SendVisitNotificationAsync(string visitorName, string visitorEmail,
            string visitorMobile, string projectName, string visitDate, string visitTime, string? message)
        {
            var adminEmail = AdminEmail();
            if (!string.IsNullOrEmpty(adminEmail))
            {
                var adminBody = $@"<h2>New Site Visit Request</h2>
<p><strong>Project:</strong> {HtmlEncode(projectName)}</p>
<p><strong>Visitor:</strong> {HtmlEncode(visitorName)} | {HtmlEncode(visitorEmail)} | {HtmlEncode(visitorMobile)}</p>
<p><strong>Date:</strong> {HtmlEncode(visitDate)} at {HtmlEncode(visitTime)}</p>
{(string.IsNullOrWhiteSpace(message) ? "" : $"<p><strong>Message:</strong> {HtmlEncode(message)}</p>")}";
                await SendAsync(adminEmail, "HydUrban Admin", $"Site Visit: {projectName} on {visitDate}", adminBody);
            }

            var visitorBody = $@"<p>Hi {HtmlEncode(visitorName)},</p>
<p>Your visit to <strong>{HtmlEncode(projectName)}</strong> is scheduled for <strong>{HtmlEncode(visitDate)}</strong> at <strong>{HtmlEncode(visitTime)}</strong>.</p>
<p>Our team will contact you at {HtmlEncode(visitorMobile)} to confirm.</p>
<p>— The HydUrban Team</p>";
            await SendAsync(visitorEmail, visitorName, $"Visit Scheduled – {projectName}", visitorBody);
        }

        public async Task SendLeadNotificationAsync(string name, string email, string mobile,
            string? projectName, string areaOfInterest, string source)
        {
            var adminEmail = AdminEmail();
            if (!string.IsNullOrEmpty(adminEmail))
            {
                var adminBody = $@"<h2>New Property Enquiry</h2>
<p><strong>Name:</strong> {HtmlEncode(name)}</p>
<p><strong>Mobile:</strong> {HtmlEncode(mobile)}</p>
<p><strong>Email:</strong> {HtmlEncode(email)}</p>
<p><strong>Project:</strong> {HtmlEncode(projectName ?? "Not specified")}</p>
<p><strong>Area:</strong> {HtmlEncode(areaOfInterest)}</p>
<p><strong>Source:</strong> {HtmlEncode(source)}</p>";
                try { await SendAsync(adminEmail, "HydUrban Admin", $"New Enquiry: {name} — {projectName ?? areaOfInterest}", adminBody); }
                catch (Exception ex) { _logger.LogError(ex, "Failed to send lead admin notification"); }
            }

            var ackBody = $@"<p>Hi {HtmlEncode(name)},</p>
<p>Thank you for your enquiry{(projectName != null ? $" about <strong>{HtmlEncode(projectName)}</strong>" : "")}. Our team will contact you within 24 hours on <strong>{HtmlEncode(mobile)}</strong>.</p>
<p>— The HydUrban Team</p>";
            try { await SendAsync(email, name, $"Thanks for your enquiry — HydUrban", ackBody); }
            catch (Exception ex) { _logger.LogError(ex, "Failed to send lead ack to {Email}", email); }
        }

        // ── Core send ──────────────────────────────────────────────────────────

        private async Task SendAsync(string toEmail, string toName, string subject, string htmlBody)
        {
            var apiKey    = _config["ResendSettings:ApiKey"] ?? _config["RESEND_API_KEY"] ?? "";
            var fromEmail = _config["ResendSettings:FromEmail"] ?? _config["SmtpSettings:FromEmail"] ?? "onboarding@resend.dev";
            var fromName  = _config["ResendSettings:FromName"]  ?? "Hyderabad Urban Realty";

            if (string.IsNullOrEmpty(apiKey))
            {
                _logger.LogWarning("ResendSettings:ApiKey not configured — email to {Email} skipped", toEmail);
                return;
            }

            var payload = new
            {
                from    = $"{fromName} <{fromEmail}>",
                to      = new[] { toEmail },
                subject = subject,
                html    = htmlBody
            };

            var client  = _http.CreateClient();
            client.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", apiKey);

            var content  = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json");

            var response = await client.PostAsync("https://api.resend.com/emails", content);

            if (!response.IsSuccessStatusCode)
            {
                var err = await response.Content.ReadAsStringAsync();
                _logger.LogError("Resend API error {Status} sending to {Email}: {Error}",
                    response.StatusCode, toEmail, err);
                throw new InvalidOperationException($"Resend API returned {response.StatusCode}: {err}");
            }

            _logger.LogInformation("Email sent via Resend to {Email}: {Subject}", toEmail, subject);
        }

        private string BaseUrl() =>
            (_config["SmtpSettings:AppBaseUrl"] ?? "https://hydurbanrealty.onrender.com").TrimEnd('/');

        private string AdminEmail() =>
            _config["ResendSettings:AdminEmail"]
            ?? _config["SmtpSettings:AdminEmail"]
            ?? _config["SmtpSettings:Username"]
            ?? "";

        private static string HtmlEncode(string s) =>
            System.Net.WebUtility.HtmlEncode(s ?? "");
    }
}
