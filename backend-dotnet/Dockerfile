# ─────────────────────────────────────────────────────────────
# Dockerfile — build context: backend-dotnet/
# Used when Render rootDir is set to backend-dotnet
# ─────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY . ./
RUN dotnet restore HyderabadUrbanReality.csproj
RUN dotnet publish HyderabadUrbanReality.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

COPY --from=build /app/publish ./

ENV ASPNETCORE_ENVIRONMENT=Production
ENV ASPNETCORE_URLS=http://+:10000
EXPOSE 10000

ENTRYPOINT ["dotnet", "HyderabadUrbanReality.dll"]
