using HyderabadUrbanReality.Core.Interfaces;
using MailKit.Net.Smtp;
using MailKit.Security;
using MimeKit;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// SMTP email service using MailKit.
    /// Configuration lives under SmtpSettings in appsettings.json.
    /// If sending fails the exception bubbles up so the caller can decide
    /// whether to surface the error or swallow it (registration always returns 201).
    /// </summary>
    public class SmtpEmailService : IEmailService
    {
        private readonly IConfiguration _config;
        private readonly ILogger<SmtpEmailService> _logger;

        public SmtpEmailService(IConfiguration config, ILogger<SmtpEmailService> logger)
        {
            _config = config;
            _logger = logger;
        }

        public async Task SendVerificationEmailAsync(string toEmail, string fullName, string rawToken)
        {
            var baseUrl = _config["SmtpSettings:AppBaseUrl"] ?? "https://www.hyderabadurbanrealty.com";
            var link    = $"{baseUrl}/verify-email?token={Uri.EscapeDataString(rawToken)}";

            var subject = "Verify your Hyderabad Urban Realty account";
            var body    = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;background:#f7f8fa;padding:32px 16px;"">
  <div style=""background:linear-gradient(135deg,#0d1f3c,#0d3b73);border-radius:10px 10px 0 0;padding:28px 32px;"">
    <img src=""{baseUrl}/assets/blue-Logo.png"" alt=""Hyderabad Urban Realty"" style=""height:36px;filter:brightness(0) invert(1);"" />
  </div>
  <div style=""background:#ffffff;border:1px solid #e8ecf2;border-top:none;border-radius:0 0 10px 10px;padding:32px;"">
    <h2 style=""color:#0d1f3c;font-size:20px;margin:0 0 12px;"">Verify your email address</h2>
    <p style=""color:#374151;font-size:14px;line-height:1.6;margin:0 0 24px;"">
      Hi {HtmlEncode(fullName)},<br><br>
      Thank you for registering. Click the button below to verify your email address.
      This link is valid for <strong>24 hours</strong>.
    </p>
    <a href=""{link}""
       style=""display:inline-block;background:#0d3b73;color:#ffffff;text-decoration:none;
              font-weight:700;font-size:14px;padding:12px 28px;border-radius:7px;
              letter-spacing:0.01em;"">
      Verify Email Address
    </a>
    <p style=""color:#94a3b8;font-size:12px;margin:24px 0 0;line-height:1.5;"">
      If you did not create an account, you can safely ignore this email.<br>
      If the button above doesn't work, copy and paste this URL into your browser:<br>
      <a href=""{link}"" style=""color:#0d3b73;word-break:break-all;"">{link}</a>
    </p>
  </div>
  <p style=""text-align:center;font-size:11px;color:#94a3b8;margin-top:16px;"">
    &copy; Hyderabad Urban Realty · <a href=""{baseUrl}"" style=""color:#94a3b8;"">hyderabadurbanrealty.com</a>
  </p>
</div>";

            await SendAsync(toEmail, fullName, subject, body);
        }

        public async Task SendPasswordResetEmailAsync(string toEmail, string fullName, string rawToken)
        {
            var baseUrl = _config["SmtpSettings:AppBaseUrl"] ?? "https://www.hyderabadurbanrealty.com";
            var link    = $"{baseUrl}/reset-password?token={Uri.EscapeDataString(rawToken)}";

            var subject = "Reset your HydUrban password";
            var body    = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;background:#f7f8fa;padding:32px 16px;"">
  <div style=""background:linear-gradient(135deg,#0d1f3c,#0d3b73);border-radius:10px 10px 0 0;padding:28px 32px;"">
    <img src=""{baseUrl}/assets/blue-Logo.png"" alt=""Hyderabad Urban Realty"" style=""height:36px;filter:brightness(0) invert(1);"" />
  </div>
  <div style=""background:#ffffff;border:1px solid #e8ecf2;border-top:none;border-radius:0 0 10px 10px;padding:32px;"">
    <h2 style=""color:#0d1f3c;font-size:20px;margin:0 0 12px;"">Reset your password</h2>
    <p style=""color:#374151;font-size:14px;line-height:1.6;margin:0 0 24px;"">
      Hi {HtmlEncode(fullName)},<br><br>
      We received a request to reset your password. Click the button below to set a new one.
      This link is valid for <strong>1 hour</strong> and can only be used once.
    </p>
    <a href=""{link}""
       style=""display:inline-block;background:#0d3b73;color:#ffffff;text-decoration:none;
              font-weight:700;font-size:14px;padding:12px 28px;border-radius:7px;
              letter-spacing:0.01em;"">
      Reset Password
    </a>
    <p style=""color:#94a3b8;font-size:12px;margin:24px 0 0;line-height:1.5;"">
      If you did not request this, you can safely ignore this email — your password will not change.<br>
      If the button above doesn't work, copy and paste this URL into your browser:<br>
      <a href=""{link}"" style=""color:#0d3b73;word-break:break-all;"">{link}</a>
    </p>
  </div>
  <p style=""text-align:center;font-size:11px;color:#94a3b8;margin-top:16px;"">
    &copy; Hyderabad Urban Realty · <a href=""{baseUrl}"" style=""color:#94a3b8;"">hyderabadurbanrealty.com</a>
  </p>
</div>";

            await SendAsync(toEmail, fullName, subject, body);
        }

        public async Task SendReviewNotificationAsync(string projectName, string reviewerName,
            string reviewerEmail, int rating, string reviewText)
        {
            var adminEmail = _config["SmtpSettings:AdminEmail"] ?? _config["SmtpSettings:Username"] ?? "";
            if (string.IsNullOrEmpty(adminEmail)) return;

            var stars = new string('★', rating) + new string('☆', 5 - rating);
            var subject = $"New Review: {HtmlEncode(projectName)} — {rating}/5 stars";
            var body = $@"
<h2 style=""font-family:sans-serif;color:#1e40af;"">New Property Review Submitted</h2>
<table style=""font-family:sans-serif;border-collapse:collapse;width:100%;max-width:560px;"">
  <tr><td style=""padding:8px;font-weight:600;color:#374151;"">Project</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(projectName)}</td></tr>
  <tr style=""background:#f9fafb;"">
      <td style=""padding:8px;font-weight:600;color:#374151;"">Reviewer</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(reviewerName)} &lt;{HtmlEncode(reviewerEmail)}&gt;</td></tr>
  <tr><td style=""padding:8px;font-weight:600;color:#374151;"">Rating</td>
      <td style=""padding:8px;color:#d97706;font-size:18px;"">{stars} ({rating}/5)</td></tr>
  <tr style=""background:#f9fafb;"">
      <td style=""padding:8px;font-weight:600;color:#374151;vertical-align:top;"">Review</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(reviewText)}</td></tr>
</table>
<p style=""font-family:sans-serif;color:#6b7280;font-size:13px;margin-top:16px;"">
  Log in to the admin panel to approve or reject this review.
</p>
<p style=""font-family:sans-serif;"">— HydUrban Notifications</p>";

            await SendAsync(adminEmail, "HydUrban Admin", subject, body);
        }

        public async Task SendVisitNotificationAsync(string visitorName, string visitorEmail,
            string visitorMobile, string projectName, string visitDate, string visitTime, string? message)
        {
            var adminEmail = _config["SmtpSettings:AdminEmail"] ?? _config["SmtpSettings:Username"] ?? "";

            // ── Email to admin ────────────────────────────────────────────
            if (!string.IsNullOrEmpty(adminEmail))
            {
                var adminSubject = $"Site Visit Request: {HtmlEncode(projectName)} on {visitDate}";
                var adminBody = $@"
<h2 style=""font-family:sans-serif;color:#1e40af;"">New Site Visit Request</h2>
<table style=""font-family:sans-serif;border-collapse:collapse;width:100%;max-width:560px;"">
  <tr><td style=""padding:8px;font-weight:600;color:#374151;"">Project</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(projectName)}</td></tr>
  <tr style=""background:#f9fafb;"">
      <td style=""padding:8px;font-weight:600;color:#374151;"">Visitor Name</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(visitorName)}</td></tr>
  <tr><td style=""padding:8px;font-weight:600;color:#374151;"">Email</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(visitorEmail)}</td></tr>
  <tr style=""background:#f9fafb;"">
      <td style=""padding:8px;font-weight:600;color:#374151;"">Mobile</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(visitorMobile)}</td></tr>
  <tr><td style=""padding:8px;font-weight:600;color:#374151;"">Preferred Date</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(visitDate)}</td></tr>
  <tr style=""background:#f9fafb;"">
      <td style=""padding:8px;font-weight:600;color:#374151;"">Preferred Time</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(visitTime)}</td></tr>
  {(string.IsNullOrWhiteSpace(message) ? "" : $@"<tr><td style=""padding:8px;font-weight:600;color:#374151;vertical-align:top;"">Message</td>
      <td style=""padding:8px;color:#111827;"">{HtmlEncode(message)}</td></tr>")}
</table>
<p style=""font-family:sans-serif;"">— HydUrban Notifications</p>";

                await SendAsync(adminEmail, "HydUrban Admin", adminSubject, adminBody);
            }

            // ── Confirmation email to visitor ─────────────────────────────
            var visitorSubject = $"Visit Scheduled – {HtmlEncode(projectName)}";
            var visitorBody = $@"
<p style=""font-family:sans-serif;"">Hi {HtmlEncode(visitorName)},</p>
<p style=""font-family:sans-serif;"">Thank you for scheduling a site visit with <strong>HydUrban Realty</strong>.</p>
<table style=""font-family:sans-serif;border-collapse:collapse;width:100%;max-width:500px;background:#f9fafb;border-radius:8px;"">
  <tr><td style=""padding:10px 16px;font-weight:600;color:#374151;"">Project</td>
      <td style=""padding:10px 16px;color:#111827;"">{HtmlEncode(projectName)}</td></tr>
  <tr><td style=""padding:10px 16px;font-weight:600;color:#374151;"">Date</td>
      <td style=""padding:10px 16px;color:#111827;"">{HtmlEncode(visitDate)}</td></tr>
  <tr><td style=""padding:10px 16px;font-weight:600;color:#374151;"">Time</td>
      <td style=""padding:10px 16px;color:#111827;"">{HtmlEncode(visitTime)}</td></tr>
</table>
<p style=""font-family:sans-serif;margin-top:16px;"">Our team will contact you at <strong>{HtmlEncode(visitorMobile)}</strong> to confirm the details.</p>
<p style=""font-family:sans-serif;color:#6b7280;font-size:13px;"">If you need to reschedule or cancel, please reply to this email or call us directly.</p>
<p style=""font-family:sans-serif;"">— The HydUrban Team</p>";

            await SendAsync(visitorEmail, visitorName, visitorSubject, visitorBody);
        }

        public async Task SendLeadNotificationAsync(string name, string email, string mobile,
            string? projectName, string areaOfInterest, string source)
        {
            var adminEmail = _config["SmtpSettings:AdminEmail"] ?? _config["SmtpSettings:Username"] ?? "";
            var appUrl     = _config["SmtpSettings:AppBaseUrl"] ?? "http://localhost:4200";
            var sourceLabel = source switch {
                "map_popup"           => "Map View Popup",
                "property_detail_page"=> "Property Detail Page",
                _                     => source
            };

            // ── Admin notification ────────────────────────────────────────
            if (!string.IsNullOrEmpty(adminEmail))
            {
                var adminSubject = $"New Enquiry: {HtmlEncode(name)} — {HtmlEncode(projectName ?? areaOfInterest)}";
                var adminBody = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:580px;margin:0 auto;"">
  <div style=""background:linear-gradient(135deg,#18215c,#0f1b66);padding:28px 32px;border-radius:12px 12px 0 0;"">
    <h2 style=""color:white;margin:0;font-size:20px;"">🏠 New Property Enquiry</h2>
    <p style=""color:rgba(255,255,255,0.7);margin:6px 0 0;font-size:13px;"">via {HtmlEncode(sourceLabel)}</p>
  </div>
  <div style=""background:white;padding:28px 32px;border:1px solid #e5e7eb;border-top:none;"">
    <table style=""width:100%;border-collapse:collapse;"">
      <tr style=""background:#f9fafb;"">
        <td style=""padding:10px 14px;font-weight:700;color:#374151;width:140px;"">Name</td>
        <td style=""padding:10px 14px;color:#111827;"">{HtmlEncode(name)}</td>
      </tr>
      <tr>
        <td style=""padding:10px 14px;font-weight:700;color:#374151;"">Mobile</td>
        <td style=""padding:10px 14px;""><a href=""tel:{HtmlEncode(mobile)}"" style=""color:#18215c;font-weight:700;"">{HtmlEncode(mobile)}</a></td>
      </tr>
      <tr style=""background:#f9fafb;"">
        <td style=""padding:10px 14px;font-weight:700;color:#374151;"">Email</td>
        <td style=""padding:10px 14px;""><a href=""mailto:{HtmlEncode(email)}"" style=""color:#18215c;"">{HtmlEncode(email)}</a></td>
      </tr>
      <tr>
        <td style=""padding:10px 14px;font-weight:700;color:#374151;"">Project</td>
        <td style=""padding:10px 14px;color:#111827;"">{HtmlEncode(projectName ?? "Not specified")}</td>
      </tr>
      <tr style=""background:#f9fafb;"">
        <td style=""padding:10px 14px;font-weight:700;color:#374151;"">Area of Interest</td>
        <td style=""padding:10px 14px;color:#111827;"">{HtmlEncode(areaOfInterest)}</td>
      </tr>
    </table>
    <div style=""margin-top:20px;display:flex;gap:12px;"">
      <a href=""https://wa.me/91{HtmlEncode(mobile.TrimStart('+').Replace(" ",""))}"" 
         style=""display:inline-block;background:#25d366;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px;"">
        📱 WhatsApp {HtmlEncode(name)}
      </a>
      <a href=""tel:{HtmlEncode(mobile)}"" 
         style=""display:inline-block;background:#18215c;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px;"">
        📞 Call Now
      </a>
    </div>
  </div>
  <p style=""font-size:12px;color:#94a3b8;text-align:center;margin-top:12px;"">
    HydUrban Admin — <a href=""{appUrl}/admin"" style=""color:#18215c;"">View all leads</a>
  </p>
</div>";
                try { await SendAsync(adminEmail, "HydUrban Admin", adminSubject, adminBody); }
                catch (Exception ex) { _logger.LogError(ex, "Failed to send lead admin notification"); }
            }

            // ── Acknowledgement to enquirer ────────────────────────────────
            var ackSubject = $"Thanks for your enquiry{(projectName != null ? $" about {HtmlEncode(projectName)}" : "")} — HydUrban";
            var ackBody = $@"
<div style=""font-family:'Segoe UI',Arial,sans-serif;max-width:540px;margin:0 auto;"">
  <div style=""background:linear-gradient(135deg,#18215c,#0f1b66);padding:28px 32px;border-radius:12px 12px 0 0;"">
    <img src=""{appUrl}/assets/blue-Logo.png"" alt=""HydUrban"" style=""height:40px;filter:brightness(0) invert(1);"" />
  </div>
  <div style=""background:white;padding:28px 32px;border:1px solid #e5e7eb;border-top:none;"">
    <h2 style=""color:#18215c;margin:0 0 12px;"">Hi {HtmlEncode(name)},</h2>
    <p style=""color:#374151;line-height:1.6;"">
      Thank you for your enquiry{(projectName != null ? $" about <strong>{HtmlEncode(projectName)}</strong>" : "")}. 
      Our team will get in touch with you within <strong>24 hours</strong> on your number 
      <strong>{HtmlEncode(mobile)}</strong>.
    </p>
    <p style=""color:#374151;line-height:1.6;"">
      In the meantime, you can explore more properties and get verified RERA data on our platform.
    </p>
    <a href=""{appUrl}/map-view"" 
       style=""display:inline-block;background:linear-gradient(135deg,#18215c,#0f1b66);color:white;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px;margin-top:8px;"">
      Explore Properties on Map
    </a>
    <hr style=""border:none;border-top:1px solid #e5e7eb;margin:24px 0;"" />
    <p style=""color:#94a3b8;font-size:12px;margin:0;"">
      You can also reach us on WhatsApp: 
      <a href=""https://wa.me/918143369988"" style=""color:#25d366;font-weight:600;"">+91 81433 69988</a>
    </p>
  </div>
  <p style=""font-size:12px;color:#94a3b8;text-align:center;margin-top:12px;"">
    © 2026 Hyderabad Urban Realty — All rights reserved
  </p>
</div>";
            try { await SendAsync(email, name, ackSubject, ackBody); }
            catch (Exception ex) { _logger.LogError(ex, "Failed to send lead acknowledgement to {Email}", email); }
        }

        // ── Private ───────────────────────────────────────────────────────────

        private async Task SendAsync(string toEmail, string toName, string subject, string htmlBody)
        {
            var host      = _config["SmtpSettings:Host"]      ?? "smtp.gmail.com";
            var port      = _config.GetValue<int>("SmtpSettings:Port", 587);
            var enableSsl = _config.GetValue<bool>("SmtpSettings:EnableSsl", true);
            var username  = _config["SmtpSettings:Username"]  ?? "";
            var password  = _config["SmtpSettings:Password"]  ?? "";
            var fromEmail = _config["SmtpSettings:FromEmail"] ?? "noreply@hydurban.com";
            var fromName  = _config["SmtpSettings:FromName"]  ?? "HydUrban";

            var message = new MimeMessage();
            message.From.Add(new MailboxAddress(fromName, fromEmail));
            message.To.Add(new MailboxAddress(toName, toEmail));
            message.Subject = subject;
            message.Body    = new TextPart(MimeKit.Text.TextFormat.Html) { Text = htmlBody };

            using var client = new SmtpClient();

            // GHSA-9j88-vvj5-vhgr mitigation: always use direct TLS (SslOnConnect) rather
            // than STARTTLS. STARTTLS is vulnerable to response injection by a MITM attacker
            // who can inject plaintext bytes before the TLS handshake completes.
            // SslOnConnect negotiates TLS immediately on connect — no plaintext phase at all.
            // Port 465 = implicit TLS (SslOnConnect). Port 587 = explicit TLS (STARTTLS) — avoid.
            // If the configured port is 587 and SSL is requested, redirect to 465 automatically.
            SecureSocketOptions socketOptions;
            int effectivePort;
            if (enableSsl)
            {
                socketOptions  = SecureSocketOptions.SslOnConnect;  // direct TLS, no STARTTLS
                effectivePort  = (port == 587) ? 465 : port;        // 465 = implicit TLS
            }
            else
            {
                socketOptions  = SecureSocketOptions.None;
                effectivePort  = port;
            }

            await client.ConnectAsync(host, effectivePort, socketOptions);
            if (!string.IsNullOrEmpty(username))
                await client.AuthenticateAsync(username, password);
            await client.SendAsync(message);
            await client.DisconnectAsync(true);

            _logger.LogInformation("Email sent to {Email}: {Subject}", toEmail, subject);
        }

        private static string HtmlEncode(string s) =>
            System.Net.WebUtility.HtmlEncode(s);
    }
}
