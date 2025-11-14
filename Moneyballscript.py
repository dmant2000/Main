import tweepy
import random
import schedule
import time
import json
import logging
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
        """Load Twitter API credentials from config file"""
        try:
            with open('twitter_config.json', 'r') as file:
                config = json.load(file)
                self.api_key = config['yp6GtuK7TPAcphVi7GlsupEzb']
                self.api_secret = config['G0fcyhgZ3bVyTBisqlCotRohaZR3v0Q9UHBrOK7ZUA3AQ4XfXy']
                self.access_token = config['2460156758-Q3y5YZKmWBBPP1ytVrDzIPL7vynaRd4q3NgdpjF']
                self.access_token_secret = config['XndafvZcQnYZwxjyuhDQ3VUuOUiW60rAgnU8p2p3ZiqZA']
        except FileNotFoundError:
            logging.error("Twitter credentials file not found!")
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
            # Add more quotes as needed
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
        tweet_text = f"\"{quote['quote']}\"\n- {quote['character']}\n#Moneyball #Baseball"
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
            
            logging.info("Successfully posted quote to Twitter")
            
        except Exception as e:
            logging.error(f"Error posting to Twitter: {str(e)}")

    def run_scheduler(self):
        """Run the scheduler for daily posts"""
        # Schedule post for specific time (e.g., 9:00 AM)
        schedule.every().day.at("09:00").do(self.post_quote)
        
        logging.info("Scheduler started")
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logging.error(f"Scheduler error: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error before retrying

def setup_twitter_config():
    """Create template for Twitter credentials"""
    config = {
        "api_key": "YOUR_API_KEY",
        "api_secret": "YOUR_API_SECRET",
        "access_token": "YOUR_ACCESS_TOKEN",
        "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET"
    }
    
    with open('twitter_config.json', 'w') as file:
        json.dump(config, file, indent=4)
    print("Created template twitter_config.json - please fill in your credentials")

if __name__ == "__main__":
    # Check if config exists, if not create template
    if not Path('twitter_config.json').exists():
        setup_twitter_config()
        print("Please fill in your Twitter API credentials in twitter_config.json")
        exit()
        
    bot = MoneyballTwitterBot()
    bot.run_scheduler()