// Gibby dialogue functionality
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
