namespace HyderabadUrbanReality.Core.DTOs
{
    public class ApiResponseDto<T>
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public T? Data { get; set; }
        public string Status { get; set; } = string.Empty;
        public List<string> Errors { get; set; } = new List<string>();
        
        public static ApiResponseDto<T> SuccessResponse(T data, string message = "Success")
        {
            return new ApiResponseDto<T>
            {
                Success = true,
                Message = message,
                Data = data,
                Status = "200"
            };
        }
        
        public static ApiResponseDto<T> ErrorResponse(string message, string status = "400")
        {
            return new ApiResponseDto<T>
            {
                Success = false,
                Message = message,
                Status = status,
                Errors = new List<string> { message }
            };
        }
    }
}