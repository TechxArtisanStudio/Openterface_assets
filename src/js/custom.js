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

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.platform-download').forEach(function(block) {
    const mainBtn = block.querySelector('.big-download-btn, .btnappstore, .btngogoleplay');
    block.querySelectorAll('.format-option').forEach(function(opt) {
      opt.addEventListener('click', function() {
        block.querySelectorAll('.format-option').forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        mainBtn.href = opt.dataset.href;
        mainBtn.textContent = 'Download ' + opt.dataset.label;

        // Special case for macOS App Store
        if (block.dataset.platform === 'macos') {
          if (opt.dataset.label === 'App Store') {
            mainBtn.classList.remove('big-download-btn', 'macos');
            mainBtn.classList.add('btnappstore');
            mainBtn.textContent = '';
          } else {
            mainBtn.classList.remove('btnappstore');
            mainBtn.classList.add('big-download-btn', 'macos');
          }
        }

        // Special case for Android Play Store
        if (block.dataset.platform === 'android') {
          if (opt.dataset.label === 'Play Store') {
            mainBtn.classList.remove('big-download-btn', 'android');
            mainBtn.classList.add('btngogoleplay');
            mainBtn.textContent = '';
          } else {
            mainBtn.classList.remove('btngogoleplay');
            mainBtn.classList.add('big-download-btn', 'android');
          }
        }

        // Special case for Linux Flathub
        if (block.dataset.platform === 'linux') {
          if (opt.dataset.label === 'FlatHub') {
            mainBtn.classList.remove('big-download-btn', 'linux');
            mainBtn.classList.add('btnflathub');
            mainBtn.textContent = '';
          } else {
            mainBtn.classList.remove('btnflathub');
            mainBtn.classList.add('big-download-btn', 'linux');
          }
        }
      });
    });
  });
});