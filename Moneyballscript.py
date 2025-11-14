import tweepy
import random
import json
import logging
import os
from datetime import datetime
from pathlib import Path

class MoneyballTwitterBot:
    def __init__(self):
        self.setup_logging()
        self.load_credentials()
        self.setup_twitter_api()
        self.load_quotes()
        
    def setup_logging(self):
        """Set up logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('twitter_bot.log'),
                logging.StreamHandler()
            ]
        )
        
    def load_credentials(self):
        """Load Twitter API credentials from environment variables or config file"""
        # Try environment variables first (for GitHub Actions)
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        
        # If not in environment, try config file
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            try:
                with open('twitter_config.json', 'r') as file:
                    config = json.load(file)
                    self.api_key = config['api_key']
                    self.api_secret = config['api_secret']
                    self.access_token = config['access_token']
                    self.access_token_secret = config['access_token_secret']
            except FileNotFoundError:
                logging.error("Twitter credentials not found in environment or config file!")
                raise
            
    def setup_twitter_api(self):
        """Initialize Twitter API client"""
        try:
            auth = tweepy.OAuthHandler(self.api_key, self.api_secret)
            auth.set_access_token(self.access_token, self.access_token_secret)
            self.api = tweepy.API(auth)
            # Verify credentials
            self.api.verify_credentials()
            logging.info("Twitter API authentication successful")
        except Exception as e:
            logging.error(f"Twitter API authentication failed: {str(e)}")
            raise

    def load_quotes(self):
        """Load Moneyball quotes from JSON file"""
        try:
            with open('moneyball_quotes.json', 'r') as file:
                self.quotes = json.load(file)
            logging.info(f"Loaded {len(self.quotes)} quotes")
        except FileNotFoundError:
            logging.info("Quotes file not found, creating default quotes")
            self.quotes = self.create_default_quotes()
            self.save_quotes()

    def create_default_quotes(self):
        """Create default list of Moneyball quotes"""
        return [
            {
                "quote": "We're all told at some point in time that we can no longer play the children's game. We just don't know when that's gonna be. Some of us are told at eighteen, some of us are told at forty, but we're all told.",
                "character": "Mets Scout",
                "used": False
            },
            {
                "quote": "How can you not be romantic about baseball?",
                "character": "Billy Beane",
                "used": False
            },
            {
                "quote": "I hate losing more than I want to win.",
                "character": "Billy Beane",
                "used": False
            },
            {
                "quote": "Your goal shouldn't be to buy players, your goal should be to buy wins.",
                "character": "Peter Brand",
                "used": False
            },
            {
                "quote": "There is an epidemic failure within the game to understand what is really happening.",
                "character": "Peter Brand",
                "used": False
            },
            {
                "quote": "47, actually 51 I don't know why I lied just then.",
                "character": "Peter Brand",
                "used": False
            },
            {
                "quote": "It's hard not to be romantic about baseball.",
                "character": "Billy Beane",
                "used": False
            },
            {
                "quote": "People who run ball clubs, they think in terms of buying players. Your goal shouldn't be to buy players, your goal should be to buy wins.",
                "character": "Peter Brand",
                "used": False
            },
            {
                "quote": "The first guy through the wall always gets bloody.",
                "character": "Billy Beane",
                "used": False
            },
            {
                "quote": "Adapt or die.",
                "character": "Billy Beane",
                "used": False
            }
        ]

    def save_quotes(self):
        """Save quotes back to JSON file"""
        with open('moneyball_quotes.json', 'w') as file:
            json.dump(self.quotes, file, indent=4)
        logging.info("Quotes saved to file")

    def get_unused_quote(self):
        """Get a random unused quote"""
        unused_quotes = [q for q in self.quotes if not q['used']]
        if not unused_quotes:
            # Reset all quotes to unused if we've used them all
            for quote in self.quotes:
                quote['used'] = False
            unused_quotes = self.quotes
            logging.info("Reset all quotes to unused")
        
        selected_quote = random.choice(unused_quotes)
        return selected_quote

    def format_tweet(self, quote):
        """Format quote for Twitter"""
        tweet_text = f"\"{quote['quote']}\"\n- {quote['character']}\n\n#Moneyball #Baseball"
        return tweet_text

    def post_quote(self):
        """Post a quote to Twitter"""
        try:
            # Get and format quote
            quote = self.get_unused_quote()
            tweet_text = self.format_tweet(quote)
            
            # Post to Twitter
            self.api.update_status(tweet_text)
            
            # Mark quote as used
            quote['used'] = True
            self.save_quotes()
            
            logging.info(f"Successfully posted quote to Twitter: {quote['quote'][:50]}...")
            return True
            
        except Exception as e:
            logging.error(f"Error posting to Twitter: {str(e)}")
            return False

if __name__ == "__main__":
    bot = MoneyballTwitterBot()
    bot.post_quote()