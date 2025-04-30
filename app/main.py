import os
import kivy
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import AsyncImage
from kivy.uix.gridlayout import GridLayout
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle
from kivy.utils import get_color_from_hex
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.uix.screenmanager import ScreenManager, Screen
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import threading
import requests
from functools import partial
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("movie_recommender_mobile.log"), logging.StreamHandler()]
)
logger = logging.getLogger("MobileMovieRecommender")

# Set minimum Kivy version
kivy.require('2.0.0')

# Define custom styles for mobile
KV_STYLING = '''
<CustomSpinner>:
    background_color: 0.1, 0.5, 0.8, 1
    color: 1, 1, 1, 1
    option_cls: "SpinnerOption"
    font_size: '14sp'

<SpinnerOption>:
    background_color: 0.2, 0.6, 0.9, 1
    color: 1, 1, 1, 1
    font_size: '14sp'
    
<CustomButton@Button>:
    background_normal: ''
    background_color: 0.1, 0.5, 0.8, 1
    color: 1, 1, 1, 1
    border_radius: [10]
    font_size: '14sp'
    size_hint: None, None
    height: '40dp'
    pos_hint: {'center_x': 0.5}
    
<MovieCard@BoxLayout>:
    orientation: 'vertical'
    size_hint_y: None
    height: 280
    padding: 5
    spacing: 5
    canvas.before:
        Color:
            rgba: 0.95, 0.95, 0.97, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8, 8, 8, 8]
            
<MobileScreenManager>:
    MainScreen:
        id: main_screen
        name: 'main_screen'
    DetailScreen:
        id: detail_screen
        name: 'detail_screen'
'''

# Load custom styling
Builder.load_string(KV_STYLING)

class CustomSpinner(Spinner):
    """Custom styled Spinner widget for mobile"""
    pass

class MovieCard(BoxLayout):
    """Mobile-optimized movie card"""
    movie_title = StringProperty("")
    movie_overview = StringProperty("")
    poster_url = StringProperty("")
    similarity_score = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super(MovieCard, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(5)
        self.spacing = dp(5)
        self.size_hint_y = None
        self.height = dp(280)
        self.bind(size=self._update_rect, pos=self._update_rect)
        
    def _update_rect(self, instance, value):
        """Update the card background"""
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.95, 0.95, 0.97, 1)
            Rectangle(pos=self.pos, size=self.size)

class LoadingPopup(Popup):
    """Loading popup with progress bar"""
    def __init__(self, **kwargs):
        super(LoadingPopup, self).__init__(**kwargs)
        self.size_hint = (0.8, None)
        self.height = dp(180)
        self.auto_dismiss = False
        self.title = "Loading..."
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        layout.add_widget(Label(text="Loading movie data...", size_hint_y=0.5, font_size='14sp'))
        
        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=0.3)
        layout.add_widget(self.progress_bar)
        
        self.content = layout
        
    def update_progress(self, value):
        """Update the progress bar value"""
        self.progress_bar.value = value

class MainScreen(Screen):
    """Main screen with search and results"""
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.app = None  # Will be set by the app
        
        # Main layout
        self.layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        
        # Create UI elements
        self._create_header()
        self._create_search_section()
        self._create_results_section()
        
        self.add_widget(self.layout)
    
    def _create_header(self):
        """Create the header section"""
        header = BoxLayout(orientation="vertical", size_hint_y=0.12, padding=[0, 5, 0, 5])
        
        with header.canvas.before:
            Color(0.1, 0.1, 0.2, 0.1)
            self.header_bg = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)
            
        title_label = Label(
            text="🎬 Movie Recommender",
            font_size='20sp',
            color=(0.1, 0.5, 0.8, 1),
            bold=True,
            size_hint_y=0.7
        )
        subtitle = Label(
            text="Find your next favorite film",
            font_size='12sp',
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=0.3
        )
        
        header.add_widget(title_label)
        header.add_widget(subtitle)
        self.layout.add_widget(header)
    
    def _update_header_bg(self, instance, value):
        """Update header background"""
        self.header_bg.pos = instance.pos
        self.header_bg.size = instance.size
    
    def _create_search_section(self):
        """Create the search and filter section"""
        search_layout = BoxLayout(orientation="vertical", size_hint_y=0.25, spacing=8)
        
        # Movie selection spinner
        self.movie_spinner = CustomSpinner(
            text="Select a Movie",
            values=[],
            size_hint=(1, None),
            height=dp(40)
        )
        
        # Genre filter
        self.genre_spinner = CustomSpinner(
            text="All Genres",
            values=["All Genres"],
            size_hint=(1, None),
            height=dp(40)
        )
        
        # Recommendation button
        self.recommend_button = Button(
            text="Get Recommendations",
            size_hint=(1, None),
            height=dp(40),
            background_color=(0.1, 0.5, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1),
            font_size='14sp',
            disabled=True
        )
        
        # Add widgets to layout
        search_layout.add_widget(self.movie_spinner)
        search_layout.add_widget(self.genre_spinner)
        search_layout.add_widget(self.recommend_button)
        
        self.layout.add_widget(search_layout)
    
    def _create_results_section(self):
        """Create the results section"""
        # Recommendations header
        self.recommendations_header = Label(
            text="Recommended Movies",
            font_size='16sp',
            color=(0.1, 0.5, 0.8, 1),
            size_hint_y=0.08,
            bold=True
        )
        self.recommendations_header.opacity = 0
        self.layout.add_widget(self.recommendations_header)
        
        # Scrollable recommendations
        self.scroll_view = ScrollView(size_hint=(1, 0.55))
        self.recommendations_grid = GridLayout(
            cols=1,
            spacing=8,
            padding=5,
            size_hint_y=None
        )
        self.recommendations_grid.bind(minimum_height=self.recommendations_grid.setter('height'))
        self.scroll_view.add_widget(self.recommendations_grid)
        self.layout.add_widget(self.scroll_view)

class DetailScreen(Screen):
    """Detail screen for selected movie"""
    def __init__(self, **kwargs):
        super(DetailScreen, self).__init__(**kwargs)
        self.app = None  # Will be set by the app
        
        # Main layout
        self.layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        
        # Back button
        self.back_button = Button(
            text="← Back to Results",
            size_hint=(None, None),
            size=(dp(150), dp(35)),
            pos_hint={'x': 0, 'top': 1},
            background_color=(0.1, 0.5, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1),
            font_size='12sp'
        )
        self.layout.add_widget(self.back_button)
        
        # Movie details content
        self.movie_content = BoxLayout(orientation="vertical", padding=5, spacing=10, size_hint_y=0.9)
        self.layout.add_widget(self.movie_content)
        
        self.add_widget(self.layout)

class MobileScreenManager(ScreenManager):
    """Screen manager for mobile navigation"""
    pass

class MobileMovieRecommenderApp(App):
    """Mobile version of the movie recommender application"""
    
    def build(self):
        """Build the application UI"""
        self.title = "Movie Recommender"
        
        # For mobile devices
        Window.clearcolor = get_color_from_hex("#FFFFFF")
        
        # Create screen manager
        self.screen_manager = MobileScreenManager()
        
        # Set references to app in screens
        self.screen_manager.get_screen('main_screen').app = self
        self.screen_manager.get_screen('detail_screen').app = self
        
        # Set up event bindings
        self._setup_bindings()
        
        # Initialize data structures
        self.df = None
        self.similarity_matrix = None
        self.genres = []
        
        # Load data in a separate thread
        self._show_loading_popup()
        threading.Thread(target=self._load_data_thread).start()
        
        return self.screen_manager
    
    def _setup_bindings(self):
        """Set up event bindings for UI elements"""
        main_screen = self.screen_manager.get_screen('main_screen')
        detail_screen = self.screen_manager.get_screen('detail_screen')
        
        # Main screen bindings
        main_screen.genre_spinner.bind(text=self._filter_by_genre)
        main_screen.recommend_button.bind(on_press=self.show_recommendations)
        
        # Detail screen bindings
        detail_screen.back_button.bind(on_press=self._go_back_to_main)
    
    def _go_back_to_main(self, instance):
        """Navigate back to main screen"""
        self.screen_manager.current = 'main_screen'
    
    def _show_loading_popup(self):
        """Show loading popup"""
        self.loading_popup = LoadingPopup()
        self.loading_popup.open()
    
    def _load_data_thread(self):
        """Load data in background thread"""
        try:
            self._load_data()
            # Update UI in the main thread
            Clock.schedule_once(self._on_data_loaded, 0)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            Clock.schedule_once(lambda dt: self._show_error_popup("Error loading data", str(e)), 0)
    
    def _load_data(self):
        """Load and preprocess movie data"""
        try:
            # Update progress
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(10), 0)
            
            # Check if dataset exists
            if not os.path.exists("dataset.csv"):
                raise FileNotFoundError("dataset.csv not found")
            
            # Load dataset
            self.df = pd.read_csv("dataset.csv")
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(30), 0)
            
            # Rename columns for consistency
            self.df.rename(columns={
                'Title': 'title',
                'Overview': 'overview',
                'Poster_Url': 'poster_url',
                'Genre': 'genre' if 'Genre' in self.df.columns else None
            }, inplace=True)
            
            # Clean data
            self.df = self.df.dropna(subset=['title', 'overview']).reset_index(drop=True)
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(50), 0)
            
            # Extract genres if available
            if 'genre' in self.df.columns:
                all_genres = []
                for genre_list in self.df['genre'].dropna():
                    try:
                        # Handle different genre formats (comma-separated, list, etc.)
                        if isinstance(genre_list, str):
                            genres = [g.strip() for g in genre_list.split(',')]
                            all_genres.extend(genres)
                    except Exception:
                        pass
                
                self.genres = ["All Genres"] + sorted(list(set(all_genres)))
            
            # Compute similarity matrix
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(60), 0)
            tfidf = TfidfVectorizer(stop_words='english')
            tfidf_matrix = tfidf.fit_transform(self.df['overview'].fillna(''))
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(80), 0)
            self.similarity_matrix = cosine_similarity(tfidf_matrix)
            Clock.schedule_once(lambda dt: self.loading_popup.update_progress(100), 0)
            
        except FileNotFoundError:
            raise FileNotFoundError("Dataset file not found. Please check if 'dataset.csv' exists in the application directory.")
        except Exception as e:
            logger.error(f"Error loading dataset: {str(e)}")
            raise Exception(f"Error loading dataset: {str(e)}")
    
    def _on_data_loaded(self, dt):
        """Callback when data is loaded"""
        main_screen = self.screen_manager.get_screen('main_screen')
        
        # Close loading popup
        self.loading_popup.dismiss()
        
        # Update UI with loaded data
        movie_titles = sorted(self.df['title'].tolist())
        main_screen.movie_spinner.values = movie_titles
        
        # Update genre spinner if genres were found
        if self.genres:
            main_screen.genre_spinner.values = self.genres
        
        # Enable recommendation button
        main_screen.recommend_button.disabled = False
        
        # Show success message
        self._show_popup("Data Loaded Successfully", 
                    f"Loaded {len(self.df)} movies.\nSelect a movie to get recommendations.")
    
    def _filter_by_genre(self, spinner, text):
        """Filter movies by selected genre"""
        main_screen = self.screen_manager.get_screen('main_screen')
        
        if text == "All Genres" or 'genre' not in self.df.columns:
            movie_titles = sorted(self.df['title'].tolist())
        else:
            filtered_movies = self.df[self.df['genre'].str.contains(text, na=False)]
            movie_titles = sorted(filtered_movies['title'].tolist())
        
        main_screen.movie_spinner.values = movie_titles
        # Reset selection if current selection is not in filtered list
        if main_screen.movie_spinner.text not in movie_titles and movie_titles:
            main_screen.movie_spinner.text = movie_titles[0]
    
    def show_recommendations(self, instance):
        """Display recommended movies"""
        main_screen = self.screen_manager.get_screen('main_screen')
        selected_movie = main_screen.movie_spinner.text
        
        if selected_movie == "Select a Movie":
            self._show_popup("No Movie Selected", "Please select a movie first.")
            return
            
        # Show loading indicator
        self.loading_popup = LoadingPopup()
        self.loading_popup.title = "Finding recommendations..."
        self.loading_popup.open()
        
        # Process recommendations in a thread
        threading.Thread(target=self._process_recommendations, args=(selected_movie,)).start()
    
    def _process_recommendations(self, selected_movie):
        """Process recommendations in background thread"""
        try:
            # Find movie index
            movie_idx = self.df[self.df['title'] == selected_movie].index[0]
            
            # Get similar movies
            similar_movies = self._get_similar_movies(movie_idx)
            
            # Get selected movie details
            selected_movie_data = self.df.iloc[movie_idx]
            
            # Update UI in main thread
            Clock.schedule_once(lambda dt: self._display_detail_view(selected_movie_data), 0)
            Clock.schedule_once(lambda dt: self._display_recommendations(similar_movies), 0)
            
        except IndexError:
            logger.error(f"Movie not found: {selected_movie}")
            Clock.schedule_once(lambda dt: self._show_popup("Movie not found", 
                                                        "Could not find the selected movie."), 0)
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            Clock.schedule_once(lambda dt: self._show_popup("Error", 
                                                        f"Error getting recommendations: {str(e)}"), 0)
        finally:
            Clock.schedule_once(lambda dt: self.loading_popup.dismiss(), 0)
    
    def _display_detail_view(self, movie_data):
        """Display selected movie in detail view"""
        detail_screen = self.screen_manager.get_screen('detail_screen')
        detail_screen.movie_content.clear_widgets()
        
        # Display selected movie details
        poster_url = movie_data.poster_url if pd.notna(movie_data.poster_url) else "https://via.placeholder.com/150x225?text=No+Image"
        
        # Create layout for poster and title
        header_layout = BoxLayout(orientation='vertical', size_hint_y=0.6)
        
        # Movie poster
        poster_layout = BoxLayout(size_hint=(1, 0.7), padding=5)
        poster_layout.add_widget(AsyncImage(
            source=poster_url,
            allow_stretch=True,
            keep_ratio=True
        ))
        header_layout.add_widget(poster_layout)
        
        # Movie title
        title_label = Label(
            text=f"{movie_data.title}",
            font_size='18sp',
            color=(0.1, 0.5, 0.8, 1),
            bold=True,
            size_hint_y=0.15,
            halign='center',
            valign='middle',
            text_size=(Window.width - dp(30), None)
        )
        header_layout.add_widget(title_label)
        
        # Add genre if available
        if 'genre' in self.df.columns and pd.notna(movie_data.genre):
            header_layout.add_widget(Label(
                text=f"Genre: {movie_data.genre}",
                font_size='14sp',
                color=(0.3, 0.3, 0.3, 1),
                size_hint_y=0.15,
                halign='center',
                valign='middle',
                text_size=(Window.width - dp(30), None)
            ))
        
        detail_screen.movie_content.add_widget(header_layout)
        
        # Movie overview in scrollview
        overview_header = Label(
            text="Overview:",
            font_size='14sp',
            color=(0.1, 0.1, 0.1, 1),
            bold=True,
            size_hint_y=None,
            height=dp(30),
            halign='left',
            text_size=(Window.width - dp(30), None)
        )
        detail_screen.movie_content.add_widget(overview_header)
        
        overview_scroll = ScrollView(size_hint_y=0.4)
        overview_label = Label(
            text=movie_data.overview if pd.notna(movie_data.overview) else "No description available",
            font_size='14sp',
            color=(0.2, 0.2, 0.2, 1),
            size_hint_y=None,
            halign='left',
            valign='top',
            text_size=(Window.width - dp(30), None)
        )
        overview_label.bind(texture_size=overview_label.setter('size'))
        overview_scroll.add_widget(overview_label)
        detail_screen.movie_content.add_widget(overview_scroll)
        
        # Switch to detail screen
        self.screen_manager.current = 'detail_screen'
    
    def _display_recommendations(self, similar_movies):
        """Display recommendations in the UI"""
        main_screen = self.screen_manager.get_screen('main_screen')
        
        # Clear previous content
        main_screen.recommendations_grid.clear_widgets()
        
        # Show recommendations header
        main_screen.recommendations_header.opacity = 1
        
        # Add recommendation cards
        for title, overview, poster_url, similarity in similar_movies:
            # Create movie card
            movie_card = BoxLayout(
                orientation='vertical', 
                size_hint_y=None, 
                height=dp(250), 
                padding=5, 
                spacing=5
            )
            
            with movie_card.canvas.before:
                Color(0.95, 0.95, 0.97, 1)
                Rectangle(pos=movie_card.pos, size=movie_card.size)
            
            # Create top layout (poster and basic info)
            top_layout = BoxLayout(orientation='horizontal', size_hint_y=0.7)
            
            # Poster image
            poster_layout = BoxLayout(size_hint_x=0.4)
            poster_layout.add_widget(AsyncImage(
                source=poster_url,
                allow_stretch=True,
                keep_ratio=True
            ))
            top_layout.add_widget(poster_layout)
            
            # Title and similarity
            info_layout = BoxLayout(orientation='vertical', size_hint_x=0.6, padding=[5, 0])
            
            title_label = Label(
                text=title,
                font_size='14sp',
                color=(0.1, 0.5, 0.8, 1),
                bold=True,
                size_hint_y=0.5,
                halign='left',
                valign='middle',
                text_size=(Window.width * 0.5, None)
            )
            info_layout.add_widget(title_label)
            
            similarity_label = Label(
                text=f"Match: {int(similarity * 100)}%",
                font_size='12sp',
                color=(0.1, 0.7, 0.1, 1),
                size_hint_y=0.3,
                halign='left',
                valign='middle',
                text_size=(Window.width * 0.5, None)
            )
            info_layout.add_widget(similarity_label)
            
            # Add a view details button
            details_button = Button(
                text="View Details",
                background_color=(0.1, 0.5, 0.8, 1),
                background_normal='',
                color=(1, 1, 1, 1),
                font_size='12sp',
                size_hint_y=0.3
            )
            
            # Bind function to show details
            movie_idx = self.df[self.df['title'] == title].index[0]
            details_button.bind(on_press=lambda btn, idx=movie_idx: self._show_movie_details(idx))
            
            info_layout.add_widget(details_button)
            top_layout.add_widget(info_layout)
            
            movie_card.add_widget(top_layout)
            
            # Overview section
            overview_label = Label(
                text=overview[:100] + ("..." if len(overview) > 100 else ""),
                font_size='12sp',
                color=(0.2, 0.2, 0.2, 1),
                size_hint_y=0.3,
                halign='left',
                valign='top',
                text_size=(Window.width - dp(30), None)
            )
            movie_card.add_widget(overview_label)
            
            main_screen.recommendations_grid.add_widget(movie_card)
    
    def _show_movie_details(self, movie_idx):
        """Show detailed view of a movie"""
        movie_data = self.df.iloc[movie_idx]
        self._display_detail_view(movie_data)
    
    def _get_similar_movies(self, idx):
        """Get similar movies from the similarity matrix"""
        try:
            distances = list(enumerate(self.similarity_matrix[idx]))
            sorted_distances = sorted(distances, key=lambda x: x[1], reverse=True)[1:6]
            
            recommendations = []
            for i, similarity in sorted_distances:
                title = self.df.iloc[i].title
                overview = self.df.iloc[i].overview if pd.notna(self.df.iloc[i].overview) else "No description available"
                poster_url = self.df.iloc[i].poster_url if pd.notna(self.df.iloc[i].poster_url) else "https://via.placeholder.com/150x225?text=No+Image"
                recommendations.append((title, overview, poster_url, similarity))
            
            return recommendations
        except Exception as e:
            logger.error(f"Error getting similar movies: {str(e)}")
            return []
    
    def _show_popup(self, title, message):
        """Show a popup with message"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(
            text=message,
            size_hint_y=0.7,
            font_size='14sp'
        ))
        
        dismiss_button = Button(
            text="OK",
            size_hint=(None, None),
            size=(dp(100), dp(40)),
            pos_hint={'center_x': 0.5},
            background_color=(0.1, 0.5, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1),
            font_size='14sp'
        )
        content.add_widget(dismiss_button)
        
        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, None),
            height=dp(200),
            auto_dismiss=True
        )
        
        dismiss_button.bind(on_press=popup.dismiss)
        popup.open()
        
    def _show_error_popup(self, title, message):
        """Show error popup"""
        self.loading_popup.dismiss()
        self._show_popup(title, message)


if __name__ == "__main__":
    try:
        # Set window size to simulate mobile device
        Window.size = (400, 700)  # Common mobile resolution
        MobileMovieRecommenderApp().run()
    except Exception as e:
        logging.error(f"Application crashed: {str(e)}")
        # Show error in a basic Kivy window
        from kivy.app import App
        from kivy.uix.label import Label
        
        class ErrorApp(App):
            def build(self):
                return Label(text=f"Application crashed: {str(e)}")
        
        ErrorApp().run()