import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { PropertyService } from '../services/property.service';

interface Message {
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  options?: string[];
}

@Component({
  standalone: false,
  selector: 'app-chatbot',
  templateUrl: './chatbot.component.html',
  styleUrls: ['./chatbot.component.css']
})
export class ChatbotComponent implements OnInit {
  isOpen = false;
  messages: Message[] = [];
  userInput = '';
  isTyping = false;

  constructor(
    private router: Router,
    private propertyService: PropertyService
  ) {}

  ngOnInit() {
    this.addBotMessage('Hi! I\'m your Hyderabad Urban Reality assistant. I can help you find properties based on location, budget, BHK, amenities, and more. How can I help you today?', [
      'Show me properties',
      'Search by budget',
      'Search by location',
      'More options'
    ]);
  }

  toggleChat() {
    this.isOpen = !this.isOpen;
  }

  closeChat() {
    this.isOpen = false;
  }

  sendMessage() {
    if (!this.userInput.trim()) return;

    const userMessage = this.userInput.trim();
    this.addUserMessage(userMessage);
    this.userInput = '';

    // Show typing indicator
    this.isTyping = true;

    // Simulate processing delay for better UX
    setTimeout(() => {
      this.processUserInput(userMessage);
      this.isTyping = false;
    }, 500);
  }

  selectOption(option: string) {
    this.addUserMessage(option);
    this.isTyping = true;
    setTimeout(() => {
      this.processUserInput(option);
      this.isTyping = false;
    }, 500);
  }

  private addUserMessage(text: string) {
    this.messages.push({
      text,
      sender: 'user',
      timestamp: new Date()
    });
    this.scrollToBottom();
  }

  private addBotMessage(text: string, options?: string[]) {
    this.messages.push({
      text,
      sender: 'bot',
      timestamp: new Date(),
      options
    });
    this.scrollToBottom();
  }

  private extractLocation(input: string): string | null {
    // Extract location from patterns like "in [location]", "near [location]", "at [location]"
    const patterns = [
      /\b(?:in|at|near|around)\s+([a-z][a-z\s]+?)(?:\s|$|,|\?)/i,
      /\bproperties?\s+(?:in|at|near|around)\s+([a-z][a-z\s]+?)(?:\s|$|,|\?)/i,
      /\b([a-z][a-z\s]+?)\s+(?:area|location|locality|properties|property)(?:\s|$|,|\?)/i
    ];

    for (const pattern of patterns) {
      const match = input.match(pattern);
      if (match && match[1]) {
        return match[1].trim();
      }
    }
    return null;
  }

  private detectIntent(input: string): string {
    const lowerInput = input.toLowerCase();
    
    // Property search intent
    if ((lowerInput.includes('show') || lowerInput.includes('see') || lowerInput.includes('view') || 
         lowerInput.includes('check') || lowerInput.includes('want') || lowerInput.includes('looking') ||
         lowerInput.includes('find') || lowerInput.includes('search')) && 
        (lowerInput.includes('properties') || lowerInput.includes('property') || 
         lowerInput.includes('projects') || lowerInput.includes('homes') ||
         lowerInput.includes('flats') || lowerInput.includes('apartments'))) {
      return 'search_property';
    }

    // Location-based search
    if (lowerInput.match(/\b(?:in|at|near|around)\s+[a-z]/i)) {
      return 'location_search';
    }

    // Comparison intent
    if (lowerInput.includes('compare')) {
      return 'compare';
    }

    // Information intent
    if (lowerInput.includes('what') || lowerInput.includes('how') || lowerInput.includes('why') ||
        lowerInput.includes('tell me') || lowerInput.includes('explain')) {
      return 'information';
    }

    return 'general';
  }

  private processUserInput(input: string) {
    const lowerInput = input.toLowerCase();
    const intent = this.detectIntent(input);

    // Extract location dynamically from any query
    const extractedLocation = this.extractLocation(input);
    
    if (extractedLocation && intent === 'location_search') {
      const locationName = extractedLocation.split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      
      this.addBotMessage(
        `Looking for properties in ${locationName}? I'll take you to our properties page where you can search for "${locationName}"!`,
        ['Browse all properties', 'Search by district']
      );
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 1500);
      return;
    }

    // Property search intent with location
    if (intent === 'search_property' && extractedLocation) {
      const locationName = extractedLocation.split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      
      this.addBotMessage(
        `Great! Let me help you find properties in ${locationName}. You'll be able to search and filter on the properties page.`,
        ['Browse properties', 'View on map']
      );
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 1500);
      return;
    }

    // Property browsing - general search
    if (intent === 'search_property') {
      this.addBotMessage('I\'ll take you to our properties page where you can browse all available projects!');
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 1000);
      return;
    }

    // District search
    if (lowerInput.includes('district')) {
      this.addBotMessage('We cover 8 districts in Hyderabad. Which district are you interested in?', [
        'Ranga Reddy',
        'Medchal-Malkajgiri',
        'Sangareddy',
        'Hyderabad',
        'Medak',
        'Vikarabad',
        'Yadadri Bhuvanagiri',
        'Siddipet'
      ]);
      return;
    }

    // Specific districts
    const districts = ['ranga reddy', 'medchal', 'sangareddy', 'hyderabad', 'medak', 'vikarabad', 'yadadri', 'siddipet'];
    for (const district of districts) {
      if (lowerInput.includes(district)) {
        this.addBotMessage(`Great choice! Let me show you properties in ${district}. Navigate to the Properties page to filter by district.`);
        setTimeout(() => {
          this.router.navigate(['/properties']);
          this.closeChat();
        }, 1500);
        return;
      }
    }

    // Budget-related queries
    if (lowerInput.includes('budget') || lowerInput.includes('afford') || lowerInput.includes('price range') ||
        (lowerInput.includes('under') && (lowerInput.includes('crore') || lowerInput.includes('lakh'))) ||
        lowerInput.includes('how much') || lowerInput.includes('cost')) {
      
      // Extract budget amount if present
      const budgetMatch = input.match(/(\d+)\s*(lakh|crore|cr|l)/i);
      if (budgetMatch) {
        const amount = budgetMatch[1];
        const unit = budgetMatch[2].toLowerCase();
        const displayAmount = unit.startsWith('c') ? `${amount} Crore` : `${amount} Lakh`;
        
        this.addBotMessage(
          `Looking for properties under ${displayAmount}? Great! You can filter properties by price range on our Properties page. Use the price filter to find options within your budget.`,
          ['Browse properties', 'View on map']
        );
      } else {
        this.addBotMessage(
          'I can help you find properties based on your budget! On the Properties page, you can:\n• Filter by price range\n• Sort by price (low to high)\n• Compare properties side-by-side\n\nWhat\'s your budget range?',
          ['Under 50 Lakh', 'Under 1 Crore', 'Browse all properties']
        );
      }
      return;
    }

    // BHK/Configuration queries
    if (lowerInput.includes('bhk') || lowerInput.includes('bedroom') || lowerInput.includes('room') ||
        lowerInput.match(/\b[1-5]\s*bhk\b/i) || lowerInput.includes('bhk options')) {
      const bhkMatch = input.match(/([1-5])\s*bhk/i);
      if (bhkMatch) {
        const bhk = bhkMatch[1];
        this.addBotMessage(
          `Looking for ${bhk} BHK properties? You can search and filter for ${bhk} BHK units on our Properties page!`,
          ['Browse properties', 'Compare options']
        );
      } else {
        this.addBotMessage(
          'We have various configurations available:\n• 1 BHK (500-700 sqft)\n• 2 BHK (900-1200 sqft)\n• 3 BHK (1400-2000 sqft)\n• 4+ BHK & Villas (2000+ sqft)\n\nWhat configuration are you looking for?',
          ['1 BHK', '2 BHK', '3 BHK', 'Browse all properties']
        );
      }
      return;
    }

    // Amenities queries
    if (lowerInput.includes('amenity') || lowerInput.includes('amenities') || lowerInput.includes('facilities') ||
        lowerInput.includes('gym') || lowerInput.includes('pool') || lowerInput.includes('parking') ||
        lowerInput.includes('clubhouse') || lowerInput.includes('park') || lowerInput.includes('security')) {
      this.addBotMessage(
        'Looking for specific amenities? Most properties on our platform offer:\n• Clubhouse & Gym\n• Swimming Pool\n• Children\'s Play Area\n• 24/7 Security\n• Parking\n• Landscaped Gardens\n\nYou can view detailed amenities on each property\'s page!',
        ['Browse properties', 'Compare amenities']
      );
      return;
    }

    // Area/Size queries
    if ((lowerInput.includes('area') || lowerInput.includes('size') || lowerInput.includes('sqft') || 
         lowerInput.includes('square feet')) && !lowerInput.includes('which area')) {
      this.addBotMessage(
        'Property sizes vary based on configuration:\n• 1 BHK: 500-700 sqft\n• 2 BHK: 900-1200 sqft\n• 3 BHK: 1400-2000 sqft\n• Villas: 2000+ sqft\n\nYou can filter by area on the Properties page!',
        ['Browse properties', 'View specifications']
      );
      return;
    }

    // Developer/Builder queries
    if (lowerInput.includes('developer') || lowerInput.includes('builder') || lowerInput.includes('promoter') ||
        lowerInput.includes('who built') || lowerInput.includes('company')) {
      this.addBotMessage(
        'All properties on our platform include verified developer/promoter information. You can:\n• View developer details\n• Check RERA registration\n• See other projects by the same developer\n\nBrowse properties to see developer information!',
        ['Browse properties', 'RERA verification']
      );
      return;
    }

    // Possession/Availability queries
    if (lowerInput.includes('possession') || lowerInput.includes('ready') || lowerInput.includes('move in') ||
        lowerInput.includes('completion') || lowerInput.includes('when available') || lowerInput.includes('delivery')) {
      this.addBotMessage(
        'We have both ready-to-move-in and under-construction properties. On the Properties page, you can:\n• Filter by possession status\n• Check completion dates\n• View project progress\n\nWhat type of possession are you looking for?',
        ['Ready to move', 'Under construction', 'Browse all']
      );
      return;
    }

    // Loan/Finance queries
    if (lowerInput.includes('loan') || lowerInput.includes('finance') || lowerInput.includes('emi') ||
        lowerInput.includes('mortgage') || lowerInput.includes('bank')) {
      this.addBotMessage(
        'Most properties are eligible for home loans from major banks. While we don\'t provide direct loan services, you can:\n• Check property RERA status (required for loans)\n• View complete property documentation\n• Contact developers for loan assistance\n\nWould you like to browse properties?',
        ['Browse properties', 'RERA verification']
      );
      return;
    }

    // Investment queries
    if (lowerInput.includes('invest') || lowerInput.includes('roi') || lowerInput.includes('return') ||
        lowerInput.includes('appreciation') || lowerInput.includes('growth')) {
      this.addBotMessage(
        'Looking for investment opportunities? Consider:\n• Location & connectivity\n• Infrastructure development\n• RERA verified projects\n• Developer reputation\n• Possession timeline\n\nBrowse our verified properties to explore investment options!',
        ['Browse properties', 'View by district', 'Compare properties']
      );
      return;
    }

    // New/Latest properties
    if (lowerInput.includes('new') || lowerInput.includes('latest') || lowerInput.includes('recent') ||
        lowerInput.includes('upcoming')) {
      this.addBotMessage(
        'You can sort properties by registration date to see the latest RERA-registered projects on our Properties page!',
        ['Browse latest properties', 'View all']
      );
      return;
    }

    // RERA information
    if (lowerInput.includes('rera') || lowerInput.includes('registration') || lowerInput.includes('verify')) {
      this.addBotMessage(
        'RERA (Real Estate Regulation and Development Act) ensures transparency in real estate. All properties on our platform are RERA-registered with verified registration numbers, promoter details, and project information.',
        ['Show RERA properties', 'Learn more about RERA']
      );
      return;
    }

    // About platform
    if (lowerInput.includes('about') || lowerInput.includes('platform') || lowerInput.includes('website')) {
      this.addBotMessage(
        'Hyderabad Urban Reality is your trusted platform for RERA-verified property information in Hyderabad. We provide comprehensive details about residential and commercial projects across 8 districts.',
        ['View About page', 'Browse properties']
      );
      return;
    }

    // Learn more about RERA
    if (lowerInput.includes('learn more about rera')) {
      this.addBotMessage(
        'RERA mandates:\n• Mandatory project registration\n• Transparent pricing\n• Timely completion\n• Quality standards\n• Buyer protection',
        ['Show RERA properties']
      );
      return;
    }

    // View About page
    if (lowerInput.includes('view about page') || lowerInput.includes('about page')) {
      this.addBotMessage('Taking you to our About page...');
      setTimeout(() => {
        this.router.navigate(['/about']);
        this.closeChat();
      }, 1000);
      return;
    }

    // Map viewing
    if (lowerInput.includes('map') || lowerInput.includes('location')) {
      this.addBotMessage('You can view all properties on an interactive map!', ['View map', 'Show properties']);
      return;
    }

    if (lowerInput.includes('view map')) {
      this.addBotMessage('Taking you to the map view...');
      setTimeout(() => {
        this.router.navigate(['/properties'], { queryParams: { view: 'map' } });
        this.closeChat();
      }, 1000);
      return;
    }

    // Pricing
    if (lowerInput.includes('price') || lowerInput.includes('cost') || lowerInput.includes('expensive') || lowerInput.includes('cheap')) {
      this.addBotMessage(
        'Property prices vary by location, size, and type. You can filter and compare properties on our Properties page to find options in your budget.',
        ['Browse properties', 'Compare properties']
      );
      return;
    }

    // Compare properties
    if (lowerInput.includes('compare')) {
      this.addBotMessage('Our comparison tool lets you compare multiple properties side-by-side!');
      setTimeout(() => {
        this.router.navigate(['/comparison']);
        this.closeChat();
      }, 1000);
      return;
    }

    // Quick button responses
    if (lowerInput.includes('under 50 lakh') || lowerInput.includes('under 1 crore') || 
        lowerInput.includes('above 1 crore') ||
        lowerInput.includes('ready to move') || lowerInput.includes('under construction') ||
        lowerInput.includes('browse all') || lowerInput.includes('browse latest properties') ||
        lowerInput.includes('view all') || lowerInput.includes('view on map') ||
        lowerInput.includes('compare options') || lowerInput.includes('compare amenities') ||
        lowerInput.includes('view specifications') || lowerInput.includes('view by district') ||
        lowerInput.includes('search by budget') || lowerInput.includes('search by location') ||
        lowerInput.includes('more options') || lowerInput.includes('budget search') ||
        lowerInput.includes('location search') || 
        lowerInput.match(/\b[1-3]\s*bhk\b/i) ||
        lowerInput === 'gachibowli' || lowerInput === 'madhapur' || lowerInput === 'kondapur') {
      
      if (lowerInput.includes('search by budget') || lowerInput.includes('budget search')) {
        this.addBotMessage('What\'s your budget range?', [
          'Under 50 Lakh',
          'Under 1 Crore',
          'Above 1 Crore',
          'Browse all properties'
        ]);
        return;
      }
      
      if (lowerInput.includes('search by location') || lowerInput.includes('location search')) {
        this.addBotMessage('Which area are you interested in?', [
          'Gachibowli',
          'Madhapur',
          'Kondapur',
          'Search by district'
        ]);
        return;
      }

      if (lowerInput.includes('more options')) {
        this.addBotMessage(
          'I can help you with:\n• Budget-based search\n• Location search\n• BHK configuration\n• Amenities\n• RERA verification\n• Investment advice\n\nWhat interests you?',
          ['Budget search', 'Location search', 'BHK options', 'Browse all']
        );
        return;
      }

      // Handle specific location buttons
      if (lowerInput === 'gachibowli' || lowerInput === 'madhapur' || lowerInput === 'kondapur') {
        const location = lowerInput.charAt(0).toUpperCase() + lowerInput.slice(1);
        this.addBotMessage(`Taking you to properties page. You can search for "${location}" there!`);
        setTimeout(() => {
          this.router.navigate(['/properties']);
          this.closeChat();
        }, 1000);
        return;
      }

      this.addBotMessage('Taking you to the properties page...');
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 800);
      return;
    }

    // Search functionality
    if (lowerInput.includes('search') || lowerInput.includes('find')) {
      this.addBotMessage(
        'You can search properties by name, location, developer, or RERA number on the Properties page. We use smart search to find the best matches!',
        ['Go to Properties']
      );
      return;
    }

    if (lowerInput.includes('go to properties')) {
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 500);
      return;
    }

    // Contact/help
    if (lowerInput.includes('contact') || lowerInput.includes('help') || lowerInput.includes('support')) {
      this.addBotMessage(
        'For inquiries, you can:\n• Email: info@hyderabadurbanrealty.com\n• Browse our FAQ section\n• Explore property details on our platform',
        ['Show properties', 'About us']
      );
      return;
    }

    // Types of properties
    if (lowerInput.includes('type') || lowerInput.includes('residential') || lowerInput.includes('commercial') || lowerInput.includes('villa') || lowerInput.includes('apartment')) {
      this.addBotMessage(
        'We have various property types:\n• Residential projects (78%)\n• Plotted developments (19%)\n• Villas & Apartments\n• Gated communities',
        ['Browse all properties']
      );
      return;
    }

    if (lowerInput.includes('browse all properties')) {
      setTimeout(() => {
        this.router.navigate(['/properties']);
        this.closeChat();
      }, 500);
      return;
    }

    // Greeting
    if (lowerInput.includes('hello') || lowerInput.includes('hi') || lowerInput.includes('hey')) {
      this.addBotMessage('Hello! How can I assist you with your property search today?', [
        'Show me properties',
        'Search by district',
        'About the platform'
      ]);
      return;
    }

    // Thank you
    if (lowerInput.includes('thank') || lowerInput.includes('thanks')) {
      this.addBotMessage('You\'re welcome! Feel free to ask if you need anything else.', [
        'Show me properties',
        'More information'
      ]);
      return;
    }

    // More information
    if (lowerInput.includes('more information') || lowerInput.includes('more info')) {
      this.addBotMessage(
        'I can help you with:\n• Property search by location\n• Budget-based filtering\n• BHK configuration search\n• Amenities information\n• RERA verification\n• Developer details\n• Possession status\n• Investment guidance\n\nWhat would you like to know?',
        ['Browse properties', 'Search by district', 'Compare properties']
      );
      return;
    }

    // Default intelligent fallback
    if (intent === 'information') {
      this.addBotMessage(
        'I\'d be happy to help! You can ask me about:\n• Properties in specific locations\n• Your budget requirements\n• BHK configurations\n• Amenities & facilities\n• RERA verification\n• Developers\n• Possession timelines\n\nTry asking something like "Show me 2 BHK properties in Gachibowli under 1 crore"',
        ['Browse properties', 'Search by district']
      );
      return;
    }

    // Default response
    this.addBotMessage(
      'I can assist you with:\n• Property search by location\n• Budget-based filtering (e.g., "under 1 crore")\n• Configuration search (1 BHK, 2 BHK, etc.)\n• Amenities & facilities\n• RERA information\n• Developer details\n• Investment guidance\n\nWhat would you like to know?',
      ['Show properties', 'Search by district', 'Compare properties']
    );
  }

  private scrollToBottom() {
    setTimeout(() => {
      const chatBody = document.querySelector('.chat-body');
      if (chatBody) {
        chatBody.scrollTop = chatBody.scrollHeight;
      }
    }, 100);
  }
}
