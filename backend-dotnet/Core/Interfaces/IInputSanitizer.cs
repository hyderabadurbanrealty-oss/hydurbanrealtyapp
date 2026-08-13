namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Interface for input sanitization service
    /// Prevents XSS attacks by sanitizing user input
    /// </summary>
    public interface IInputSanitizer
    {
        /// <summary>
        /// Sanitizes potentially dangerous HTML/script content from user input
        /// </summary>
        string Sanitize(string input);
    }
}
