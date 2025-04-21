window.onload = function () {
    // Hide the loading message when tweets are loaded
    var hideLoadingMessage = function () {
        var loadingMessage = document.getElementById('loadingMessage');
        if (loadingMessage) {
            loadingMessage.style.display = 'none';
        }
    };

    // Check if the Twitter widgets script is loaded
    if (typeof twttr !== 'undefined') {
        twttr.widgets.load(
            document.getElementById("twitter-feed")
        );
        twttr.events.bind('loaded', function (event) {
            // Hide loading message
            hideLoadingMessage();

            // Find all twitter tweets and show them
            var tweets = document.querySelectorAll('.twitter-tweet');
            tweets.forEach(function (tweet) {
                tweet.classList.add('twitter-tweet-loaded');
            });

            // Unhide the twitter feed
            var loadingMessage = document.getElementById('twitter-feed');
            if (loadingMessage) {
                loadingMessage.style.display = 'block';
            }
        });
    } else {
        var loadingMessage = document.getElementById('twitter-feed');
        if (loadingMessage) {
            loadingMessage.style.display = 'none';
        }
    }

    // New Twitter navigation code
    const initTwitterNavigation = () => {
        const twitterPosts = document.querySelector('.twitter-posts');
        const prevButton = document.querySelector('.twitter-nav-prev');
        const nextButton = document.querySelector('.twitter-nav-next');

        if (twitterPosts && prevButton && nextButton) {
            const tweetWidth = 300; // Width of each tweet
            const scrollAmount = tweetWidth + 16; // Width + gap

            prevButton.addEventListener('click', () => {
                twitterPosts.scrollBy({
                    left: -scrollAmount,
                    behavior: 'smooth'
                });
            });

            nextButton.addEventListener('click', () => {
                twitterPosts.scrollBy({
                    left: scrollAmount,
                    behavior: 'smooth'
                });
            });
        }
    };

    // Initialize after a short delay to ensure tweets are loaded
    setTimeout(initTwitterNavigation, 200);
};

document.addEventListener('DOMContentLoaded', function () {
    const dialogue = document.querySelector('.gibby-dialogue');

    function toggleDialogue() {
        dialogue.style.display = 'block';
        setTimeout(() => {
            dialogue.style.display = 'none';
            setTimeout(toggleDialogue, 2000); // Wait 2 seconds before showing again
        }, 20000); // Show for 20 seconds
    }

    // Start the cycle after 1 second
    setTimeout(toggleDialogue, 1000);
});

// Slideshow functionality
document.addEventListener("DOMContentLoaded", function () {
    let slideIndex = 0;
    showSlides();

    function showSlides() {
        const slides = document.getElementsByClassName("slides");

        // Hide all slides
        for (let i = 0; i < slides.length; i++) {
            slides[i].style.display = "none";
        }

        // Increment slide index and reset if needed
        slideIndex++;
        if (slideIndex > slides.length) {
            slideIndex = 1;
        }

        // Show the current slide
        slides[slideIndex - 1].style.display = "block";

        // Change slide every 6 seconds
        setTimeout(showSlides, 6000);
    }
});
