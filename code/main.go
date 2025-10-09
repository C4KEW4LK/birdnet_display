package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"html/template"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	qrcode "github.com/skip2/go-qrcode"
)

const (
	DefaultAPIURL        = "http://localhost:8080"
	APIEndpoint          = "api/v2/detections/recent"
	ServerPort           = 5000
	PinnedSpeciesFile    = "pinned_species.json"
	PinnedDurationHours  = 24
	CacheDirectory       = "static/bird_images_cache"
	SpeciesFile          = "species_list.csv"
)

var (
	apiURL = DefaultAPIURL
)

// Global cache
var (
	detectionCache = struct {
		sync.RWMutex
		ID      string
		RawData []*BirdData
	}{}
)

// Data structures
type BirdData struct {
	Name            string  `json:"name"`
	TimeRaw         string  `json:"time_raw"`
	TimeDisplay     string  `json:"time_display"`
	Confidence      string  `json:"confidence"`
	ConfidenceValue int     `json:"confidence_value"`
	ImageURL        string  `json:"image_url"`
	Copyright       string  `json:"copyright"`
	IsNewSpecies    bool    `json:"is_new_species"`
	IsOffline       bool    `json:"is_offline,omitempty"`
	IsPinned        bool    `json:"is_pinned,omitempty"`
}

type PinnedSpecies struct {
	PinnedUntil string `json:"pinned_until"`
	Dismissed   bool   `json:"dismissed"`
}

type Detection struct {
	CommonName    string  `json:"commonName"`
	Date          string  `json:"date"`
	Time          string  `json:"time"`
	Confidence    float64 `json:"confidence"`
	SpeciesCode   string  `json:"speciesCode"`
	IsNewSpecies  bool    `json:"isNewSpecies"`
}

func main() {
	// Parse command-line flags
	apiURLFlag := flag.String("apiURL", DefaultAPIURL, "BirdNET-Go API URL (e.g., http://192.168.1.169:8080)")
	portFlag := flag.Int("port", ServerPort, "Server port")
	flag.Parse()

	// Update global variables from flags
	apiURL = strings.TrimSuffix(*apiURLFlag, "/")
	serverPort := *portFlag

	log.Printf("BirdNET-Go API URL: %s\n", apiURL)
	log.Printf("Server will start on port: %d\n", serverPort)

	gin.SetMode(gin.ReleaseMode)
	r := gin.Default()

	// Load HTML templates
	funcMap := template.FuncMap{
		"range": func(n int) []int {
			result := make([]int, n)
			for i := range result {
				result[i] = i
			}
			return result
		},
		"add": func(a, b int) int {
			return a + b
		},
	}
	r.SetFuncMap(funcMap)
	r.LoadHTMLGlob("templates/*")
	r.Static("/static", "./static")

	// Routes
	r.GET("/", indexHandler)
	r.GET("/data", dataHandler)
	r.GET("/qr_code.png", qrCodeHandler)
	r.GET("/audio_status", audioStatusHandler)
	r.POST("/brightness", setBrightnessHandler)
	r.POST("/reboot", rebootHandler)
	r.POST("/poweroff", poweroffHandler)
	r.GET("/api/pinned_species", getPinnedSpeciesHandler)
	r.POST("/api/dismiss_pinned/:species_name", dismissPinnedHandler)
	r.POST("/api/dismiss_all_pinned", dismissAllPinnedHandler)

	addr := fmt.Sprintf("0.0.0.0:%d", serverPort)
	log.Printf("Starting server on http://%s\n", addr)
	if err := r.Run(addr); err != nil {
		log.Fatal(err)
	}
}

// Handlers
func indexHandler(c *gin.Context) {
	birds, apiDown := getBirdData()
	refreshInterval := 5
	if apiDown {
		refreshInterval = 30
	}

	// Use configured API URL for server_url
	serverURL := apiURL
	if strings.Contains(apiURL, "localhost") || strings.Contains(apiURL, "127.0.0.1") {
		ip := getLocalIP()
		port := "8080"
		if strings.Contains(apiURL, ":") {
			parts := strings.Split(apiURL, ":")
			if len(parts) >= 3 {
				port = parts[2]
			}
		}
		serverURL = fmt.Sprintf("http://%s:%s", ip, port)
	}

	c.HTML(http.StatusOK, "index.html", gin.H{
		"birds":            birds,
		"refresh_interval": refreshInterval,
		"api_is_down":      apiDown,
		"server_url":       serverURL,
	})
}

func dataHandler(c *gin.Context) {
	birds, apiDown := getBirdData()
	c.JSON(http.StatusOK, gin.H{
		"birds":       birds,
		"api_is_down": apiDown,
	})
}

func qrCodeHandler(c *gin.Context) {
	// Use the configured API URL for QR code
	// If it's localhost, use the local IP instead
	qrURL := apiURL
	if strings.Contains(apiURL, "localhost") || strings.Contains(apiURL, "127.0.0.1") {
		ip := getLocalIP()
		// Extract port from apiURL if present
		port := "8080"
		if strings.Contains(apiURL, ":") {
			parts := strings.Split(apiURL, ":")
			if len(parts) >= 3 {
				port = parts[2]
			}
		}
		qrURL = fmt.Sprintf("http://%s:%s", ip, port)
	}

	png, err := qrcode.Encode(qrURL, qrcode.Medium, 256)
	if err != nil {
		c.String(http.StatusInternalServerError, "Failed to generate QR code")
		return
	}

	c.Data(http.StatusOK, "image/png", png)
}

func audioStatusHandler(c *gin.Context) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get("http://10.42.0.50/api/status")

	isConnected := false
	if err == nil {
		defer resp.Body.Close()
		var status map[string]interface{}
		if json.NewDecoder(resp.Body).Decode(&status) == nil {
			if streaming, ok := status["streaming"].(bool); ok {
				isConnected = streaming
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{"connected": isConnected})
}

func setBrightnessHandler(c *gin.Context) {
	var req struct {
		Brightness int `json:"brightness"`
	}

	if err := c.BindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "Invalid request"})
		return
	}

	if req.Brightness < 0 || req.Brightness > 255 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "Invalid brightness value"})
		return
	}

	cmd := exec.Command("bash", "-c", fmt.Sprintf("echo %d | sudo tee /sys/class/backlight/10-0045/brightness", req.Brightness))
	if err := cmd.Run(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "brightness": req.Brightness})
}

func rebootHandler(c *gin.Context) {
	log.Println("Executing reboot command...")
	go exec.Command("sudo", "reboot").Run()
	c.JSON(http.StatusOK, gin.H{"status": "rebooting"})
}

func poweroffHandler(c *gin.Context) {
	log.Println("Executing power off command...")
	go exec.Command("sudo", "poweroff").Run()
	c.JSON(http.StatusOK, gin.H{"status": "shutting down"})
}

func getPinnedSpeciesHandler(c *gin.Context) {
	activePinned := getActivePinnedSpecies()
	now := time.Now()
	result := []map[string]interface{}{}

	for name, data := range activePinned {
		pinnedUntil, _ := time.Parse(time.RFC3339, data.PinnedUntil)
		timeRemaining := pinnedUntil.Sub(now)
		hoursRemaining := int(timeRemaining.Hours())

		result = append(result, map[string]interface{}{
			"name":            name,
			"hours_remaining": hoursRemaining,
			"pinned_until":    data.PinnedUntil,
		})
	}

	c.JSON(http.StatusOK, result)
}

func dismissPinnedHandler(c *gin.Context) {
	speciesName := c.Param("species_name")

	if dismissPinnedSpecies(speciesName) {
		c.JSON(http.StatusOK, gin.H{"status": "success", "message": fmt.Sprintf("%s dismissed", speciesName)})
	} else {
		c.JSON(http.StatusNotFound, gin.H{"status": "error", "message": fmt.Sprintf("%s not found in pinned list", speciesName)})
	}
}

func dismissAllPinnedHandler(c *gin.Context) {
	pinned := loadPinnedSpecies()
	for name := range pinned {
		data := pinned[name]
		data.Dismissed = true
		pinned[name] = data
	}
	savePinnedSpecies(pinned)
	c.JSON(http.StatusOK, gin.H{"status": "success", "message": "All pinned species dismissed"})
}

// Pinned species management
func loadPinnedSpecies() map[string]PinnedSpecies {
	data, err := os.ReadFile(PinnedSpeciesFile)
	if err != nil {
		return make(map[string]PinnedSpecies)
	}

	var pinned map[string]PinnedSpecies
	if err := json.Unmarshal(data, &pinned); err != nil {
		return make(map[string]PinnedSpecies)
	}

	return pinned
}

func savePinnedSpecies(pinned map[string]PinnedSpecies) {
	data, err := json.MarshalIndent(pinned, "", "  ")
	if err != nil {
		log.Printf("Error marshaling pinned species: %v\n", err)
		return
	}

	if err := os.WriteFile(PinnedSpeciesFile, data, 0644); err != nil {
		log.Printf("Error saving pinned species: %v\n", err)
	}
}

func addPinnedSpecies(speciesName string) {
	pinned := loadPinnedSpecies()
	if _, exists := pinned[speciesName]; !exists {
		pinned[speciesName] = PinnedSpecies{
			PinnedUntil: time.Now().Add(PinnedDurationHours * time.Hour).Format(time.RFC3339),
			Dismissed:   false,
		}
		savePinnedSpecies(pinned)
	}
}

func dismissPinnedSpecies(speciesName string) bool {
	pinned := loadPinnedSpecies()
	if data, exists := pinned[speciesName]; exists {
		data.Dismissed = true
		pinned[speciesName] = data
		savePinnedSpecies(pinned)
		return true
	}
	return false
}

func getActivePinnedSpecies() map[string]PinnedSpecies {
	pinned := loadPinnedSpecies()
	active := make(map[string]PinnedSpecies)
	now := time.Now()
	modified := false

	for name, data := range pinned {
		pinnedUntil, err := time.Parse(time.RFC3339, data.PinnedUntil)
		if err != nil {
			continue
		}

		if !data.Dismissed && now.Before(pinnedUntil) {
			active[name] = data
		} else if !now.Before(pinnedUntil) {
			delete(pinned, name)
			modified = true
		}
	}

	if modified {
		savePinnedSpecies(pinned)
	}

	return active
}

// Network helpers
func getLocalIP() string {
	conn, err := net.Dial("udp", "10.255.255.255:1")
	if err != nil {
		return "127.0.0.1"
	}
	defer conn.Close()

	localAddr := conn.LocalAddr().(*net.UDPAddr)
	return localAddr.IP.String()
}

// Time formatting
func parseAbsoluteTimeToSecondsAgo(timeStr string) float64 {
	if timeStr == "" {
		return 0
	}

	t, err := time.Parse("2006-01-02 15:04:05", timeStr)
	if err != nil {
		return 0
	}

	diff := time.Since(t).Seconds()
	if diff < 0 {
		return 0
	}
	return diff
}

func formatSecondsAgo(seconds float64) string {
	if seconds < 60 {
		return fmt.Sprintf("%ds ago", int(seconds))
	}
	minutes := seconds / 60
	if minutes < 60 {
		return fmt.Sprintf("%dm ago", int(minutes))
	}
	hours := minutes / 60
	if hours < 24 {
		return fmt.Sprintf("%dh ago", int(hours))
	}
	return fmt.Sprintf("%dd ago", int(hours/24))
}

// Image cache
func getCachedImage(speciesName string) map[string]string {
	folderName := strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == ' ' || r == '_' {
			return r
		}
		return -1
	}, speciesName)
	folderName = strings.TrimSpace(strings.ReplaceAll(folderName, " ", "_"))

	speciesDir := filepath.Join(CacheDirectory, folderName)
	entries, err := os.ReadDir(speciesDir)
	if err != nil {
		return nil
	}

	var images []string
	for _, entry := range entries {
		if !entry.IsDir() {
			name := strings.ToLower(entry.Name())
			if strings.HasSuffix(name, ".png") || strings.HasSuffix(name, ".jpg") || strings.HasSuffix(name, ".jpeg") {
				images = append(images, entry.Name())
			}
		}
	}

	if len(images) == 0 {
		return nil
	}

	sort.Strings(images)
	chosenImage := images[time.Now().UnixNano()%int64(len(images))]

	copyright := ""
	attrPath := filepath.Join(speciesDir, strings.TrimSuffix(chosenImage, filepath.Ext(chosenImage))+".txt")
	if data, err := os.ReadFile(attrPath); err == nil {
		copyright = strings.TrimSpace(string(data))
	}

	imageURL := "/static/" + filepath.ToSlash(filepath.Join(filepath.Base(CacheDirectory), folderName, chosenImage))

	return map[string]string{
		"image_url": imageURL,
		"copyright": copyright,
	}
}

// Data fetching
func checkImageURLFast(url string) bool {
	client := &http.Client{Timeout: 500 * time.Millisecond}
	resp, err := client.Head(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

func parseV2DetectionItem(detection Detection) *BirdData {
	name := detection.CommonName
	if name == "" {
		name = "Unknown Species"
	}

	timeRaw := strings.TrimSpace(detection.Date + " " + detection.Time)
	confidenceValue := int(detection.Confidence * 100)

	imageURL := ""
	if detection.SpeciesCode != "" {
		imageURL = fmt.Sprintf("%s/api/v2/species/%s/thumbnail", apiURL, detection.SpeciesCode)
	}

	return &BirdData{
		Name:            name,
		TimeRaw:         timeRaw,
		ConfidenceValue: confidenceValue,
		ImageURL:        imageURL,
		Copyright:       "",
		IsNewSpecies:    detection.IsNewSpecies,
	}
}

func getOfflineFallbackData() []BirdData {
	log.Println("[INFO] Loading data from local cache.")
	speciesList := loadSpeciesFromFile(SpeciesFile)
	if len(speciesList) == 0 {
		return []BirdData{}
	}

	numToSample := 4
	if len(speciesList) < 4 {
		numToSample = len(speciesList)
	}

	// Random sampling
	indices := make([]int, len(speciesList))
	for i := range indices {
		indices[i] = i
	}

	// Shuffle
	for i := len(indices) - 1; i > 0; i-- {
		j := time.Now().UnixNano() % int64(i+1)
		indices[i], indices[j] = indices[j], indices[i]
	}

	var fallbackData []BirdData
	for i := 0; i < numToSample; i++ {
		commonName := speciesList[indices[i]][0]
		cached := getCachedImage(commonName)
		if cached != nil {
			fallbackData = append(fallbackData, BirdData{
				Name:            commonName,
				TimeDisplay:     "Offline",
				Confidence:      "0%",
				ConfidenceValue: 0,
				ImageURL:        cached["image_url"],
				Copyright:       cached["copyright"],
				TimeRaw:         "",
				IsOffline:       true,
			})
		}
	}

	return fallbackData
}

func getBirdData() ([]BirdData, bool) {
	apiEndpoint := apiURL + "/" + APIEndpoint

	client := &http.Client{Timeout: 10 * time.Second}
	req, _ := http.NewRequest("GET", apiEndpoint, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	q := req.URL.Query()
	q.Add("limit", "50")
	req.URL.RawQuery = q.Encode()

	resp, err := client.Do(req)
	if err != nil {
		log.Println("[INFO] BirdNET-Go API unavailable, using offline mode")
		return getOfflineFallbackData(), true
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return getOfflineFallbackData(), true
	}

	body, _ := io.ReadAll(resp.Body)
	var detections []Detection
	if err := json.Unmarshal(body, &detections); err != nil {
		return getOfflineFallbackData(), true
	}

	if len(detections) == 0 {
		return getOfflineFallbackData(), true
	}

	var allParsed []*BirdData
	for _, det := range detections {
		if parsed := parseV2DetectionItem(det); parsed != nil {
			allParsed = append(allParsed, parsed)
		}
	}

	if len(allParsed) == 0 {
		return getOfflineFallbackData(), true
	}

	// Process new species
	for _, bird := range allParsed {
		if bird.IsNewSpecies {
			addPinnedSpecies(bird.Name)
		}
	}

	// Get active pinned species
	activePinned := getActivePinnedSpecies()

	var pinnedBirds []*BirdData
	var unpinnedBirds []*BirdData

	for _, bird := range allParsed {
		if _, isPinned := activePinned[bird.Name]; isPinned {
			bird.IsPinned = true
			// Check if already in pinned list
			found := false
			for _, pb := range pinnedBirds {
				if pb.Name == bird.Name {
					found = true
					break
				}
			}
			if !found {
				pinnedBirds = append(pinnedBirds, bird)
			}
		} else {
			bird.IsPinned = false
			unpinnedBirds = append(unpinnedBirds, bird)
		}
	}

	// Get unique unpinned
	var uniqueUnpinned []*BirdData
	seenNames := make(map[string]bool)
	for _, bird := range unpinnedBirds {
		if !seenNames[bird.Name] {
			uniqueUnpinned = append(uniqueUnpinned, bird)
			seenNames[bird.Name] = true
		}
	}

	// Combine pinned + unpinned, limit to 4
	finalList := append(pinnedBirds, uniqueUnpinned...)
	if len(finalList) > 4 {
		finalList = finalList[:4]
	}

	// Check images for final 4
	for _, bird := range finalList {
		if bird.ImageURL != "" {
			if !checkImageURLFast(bird.ImageURL) {
				if cached := getCachedImage(bird.Name); cached != nil {
					bird.ImageURL = cached["image_url"]
					bird.Copyright = cached["copyright"]
				}
			}
		} else {
			if cached := getCachedImage(bird.Name); cached != nil {
				bird.ImageURL = cached["image_url"]
				bird.Copyright = cached["copyright"]
			}
		}
	}

	// Create cache ID
	var idParts []string
	for _, d := range finalList {
		idParts = append(idParts, d.Name+"_"+d.TimeRaw)
	}
	newID := strings.Join(idParts, "-")

	detectionCache.Lock()
	var dataToProcess []*BirdData
	if newID == detectionCache.ID {
		dataToProcess = detectionCache.RawData
	} else {
		detectionCache.RawData = finalList
		detectionCache.ID = newID
		dataToProcess = finalList
	}
	detectionCache.Unlock()

	// Format display data
	var displayData []BirdData
	for _, bird := range dataToProcess {
		birdCopy := *bird
		birdCopy.TimeDisplay = formatSecondsAgo(parseAbsoluteTimeToSecondsAgo(bird.TimeRaw))
		birdCopy.Confidence = fmt.Sprintf("%d%%", bird.ConfidenceValue)
		displayData = append(displayData, birdCopy)
	}

	return displayData, false
}

func loadSpeciesFromFile(filename string) [][2]string {
	data, err := os.ReadFile(filename)
	if err != nil {
		return nil
	}

	lines := strings.Split(string(data), "\n")
	var species [][2]string

	for i, line := range lines {
		if i == 0 {
			continue // Skip header
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		parts := strings.Split(line, ",")
		if len(parts) >= 2 {
			common := strings.TrimSpace(parts[0])
			scientific := strings.TrimSpace(parts[1])
			if common != "" && scientific != "" {
				species = append(species, [2]string{common, scientific})
			}
		}
	}

	return species
}
