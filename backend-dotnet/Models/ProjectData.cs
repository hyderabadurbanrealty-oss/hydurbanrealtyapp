namespace HyderabadUrbanReality.Models
{
    public class ProjectData
    {
        public string? Id { get; set; }
        public string? ProjectName { get; set; }
        public string? ProjectStatus { get; set; }
        public string? ProjectType { get; set; }
        public string? ApprovedDate { get; set; }
        public string? ProposedDateOfCompletion { get; set; }
        public string? TotalArea { get; set; }
        public string? NetArea { get; set; }
        public string? ApprovedBuiltUpArea { get; set; }
        public string? MortgageArea { get; set; }
        public string? BoundariesEast { get; set; }
        public string? BoundariesWest { get; set; }
        public string? BoundariesNorth { get; set; }
        public string? BoundariesSouth { get; set; }
        public string? State { get; set; }
        public string? District { get; set; }
        public string? Mandal { get; set; }
        public string? VillageCityTown { get; set; }
        public string? PinCode { get; set; }
        public string? Street { get; set; }
        public string? Locality { get; set; }
        public string? LandMark { get; set; }
        public string? Name { get; set; }
        public string? OrganizationType { get; set; }
        public string? PastExperience { get; set; }
        public string? CriminalCase { get; set; }
        public string? AuthorityName { get; set; }
        public string? PlanApprovalNumber { get; set; }
        public string? SyNo { get; set; }
        public string? BankName { get; set; }
        public string? BranchName { get; set; }
    }

    public class LoginRequest
    {
        public string? Username { get; set; }
        public string? Password { get; set; }
    }

    public class LoginResponse
    {
        public string Status { get; set; } = string.Empty;
        public string? Message { get; set; }
    }
}
