// Include GSAP CDN
const script = document.createElement('script');
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.11.0/gsap.min.js';
document.head.appendChild(script);

// Wait for the GSAP script to load before adding event listeners
script.onload = () => {
  document.querySelectorAll('a, button').forEach((element) => {
    element.addEventListener('mouseenter', () => {
      gsap.to(element, { scale: 1.1, duration: 0.3 });
    });

    element.addEventListener('mouseleave', () => {
      gsap.to(element, { scale: 1.0, duration: 0.3 });
    });
  });
};

