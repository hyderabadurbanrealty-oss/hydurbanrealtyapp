namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Transactional email delivery contract.
    /// </summary>
    public interface IEmailService
    {
        /// <summary>Sends an email verification link to a newly registered user.</summary>
        Task SendVerificationEmailAsync(string toEmail, string fullName, string rawToken);

        /// <summary>Sends a password reset link.</summary>
        Task SendPasswordResetEmailAsync(string toEmail, string fullName, string rawToken);

        /// <summary>Notifies the admin about a new review submission.</summary>
        Task SendReviewNotificationAsync(string projectName, string reviewerName, string reviewerEmail, int rating, string reviewText);

        /// <summary>Notifies the admin about a new schedule-visit request and confirms to the visitor.</summary>
        Task SendVisitNotificationAsync(string visitorName, string visitorEmail, string visitorMobile,
            string projectName, string visitDate, string visitTime, string? message);

        /// <summary>Notifies the admin about a new lead/enquiry and sends an acknowledgement to the enquirer.</summary>
        Task SendLeadNotificationAsync(string name, string email, string mobile,
            string? projectName, string areaOfInterest, string source);
    }
}
