using HyderabadUrbanReality.Core.Interfaces;
using Ganss.Xss;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Service for sanitizing user input to prevent XSS attacks
    /// Follows Single Responsibility - handles input sanitization only
    /// </summary>
    public class InputSanitizer : IInputSanitizer
    {
        private readonly HtmlSanitizer _sanitizer;

        public InputSanitizer()
        {
            _sanitizer = new HtmlSanitizer();
            // Strip all HTML tags for maximum security
            _sanitizer.AllowedTags.Clear();
            _sanitizer.AllowedAttributes.Clear();
            _sanitizer.AllowedCssProperties.Clear();
        }

        /// <inheritdoc />
        public string Sanitize(string input)
        {
            if (string.IsNullOrWhiteSpace(input))
                return input;
            
            // Remove all HTML tags and dangerous content
            return _sanitizer.Sanitize(input);
        }
    }
}
