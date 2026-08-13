using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using System.Security.Claims;

namespace HyderabadUrbanReality.Core.Filters
{
    /// <summary>
    /// Action filter that returns 403 with "email_not_verified" for users whose
    /// account has not completed email verification (Req 17.4).
    /// Apply to any controller or action that requires a verified account.
    /// </summary>
    public class RequireVerifiedEmailAttribute : ActionFilterAttribute
    {
        public override async Task OnActionExecutionAsync(
            ActionExecutingContext context,
            ActionExecutionDelegate next)
        {
            var userRepo = context.HttpContext.RequestServices
                .GetRequiredService<IUserRepository>();

            var subClaim = context.HttpContext.User.FindFirstValue(ClaimTypes.NameIdentifier)
                        ?? context.HttpContext.User.FindFirstValue("sub");

            if (subClaim is null || !Guid.TryParse(subClaim, out var userId))
            {
                context.Result = new UnauthorizedObjectResult(new { error = "invalid_token" });
                return;
            }

            var user = await userRepo.GetByIdAsync(userId);
            if (user is null || !user.IsVerified)
            {
                context.Result = new ObjectResult(
                    new { error = "email_not_verified", message = "Please verify your email first." })
                { StatusCode = 403 };
                return;
            }

            await next();
        }
    }
}
