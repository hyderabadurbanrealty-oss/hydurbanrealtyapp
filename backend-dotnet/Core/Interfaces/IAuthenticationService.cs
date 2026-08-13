namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Defines contract for authentication operations
    /// Follows Single Responsibility Principle - handles auth only
    /// </summary>
    public interface IAuthenticationService
    {
        /// <summary>
        /// Authenticates user credentials
        /// </summary>
        Task<bool> AuthenticateAsync(string username, string password);
        
        /// <summary>
        /// Validates if user is authenticated admin
        /// </summary>
        bool IsAuthenticated(string sessionToken);
    }
}
