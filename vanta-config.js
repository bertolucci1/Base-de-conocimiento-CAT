/**
 * CONFIGURACIÓN DE VANTA.NET - Fondo 3D Interactivo
 * 
 * Edita estos valores para personalizar el fondo dinámicamente
 * Los cambios se aplicarán automáticamente al recargar la página
 */

const VANTA_CONFIG = {
    // Color de la red/líneas (en hexadecimal)
    color: 0xff3f81,                // Rosa/Magenta
    
    // Color de fondo
    backgroundColor: 0x23153c,      // Púrpura oscuro
    
    // Cantidad de puntos en la red
    points: 10,
    
    // Distancia máxima entre puntos para conectarlos con líneas
    maxDistance: 20,
    
    // Espaciado entre puntos
    spacing: 15,
    
    // Mostrar u ocultar los puntos
    showDots: true,
    
    // Controles
    mouseControls: true,            // Reacciona al movimiento del mouse
    touchControls: true,            // Soporta toque en dispositivos móviles
    gyroControls: false,            // Controles por giroscopio (para móviles)
    
    // Dimensiones mínimas
    minHeight: 200.00,
    minWidth: 200.00,
    
    // Escala
    scale: 1.00,
    scaleMobile: 1.00
};

/**
 * PRESETS DE CONFIGURACIÓN
 * Descomenta el que quieras usar
 */

// Preset Cyberpunk (Rosa/Magenta con púrpura oscuro)
/*
const VANTA_CONFIG = {
    color: 0xff3f81,
    backgroundColor: 0x23153c,
    points: 10,
    maxDistance: 20,
    spacing: 15,
    showDots: true,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00
};
*/

// Preset Azul Neón (Cyan/Azul con fondo oscuro)
/*
const VANTA_CONFIG = {
    color: 0x00d4ff,
    backgroundColor: 0x0a0e27,
    points: 15,
    maxDistance: 25,
    spacing: 20,
    showDots: true,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00
};
*/

// Preset Verde Neón (Muy futurista)
/*
const VANTA_CONFIG = {
    color: 0x00ff88,
    backgroundColor: 0x0d1117,
    points: 12,
    maxDistance: 22,
    spacing: 18,
    showDots: true,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00
};
*/

// Preset Minimalista (Pocos puntos)
/*
const VANTA_CONFIG = {
    color: 0x06b6d4,
    backgroundColor: 0x121822,
    points: 5,
    maxDistance: 15,
    spacing: 20,
    showDots: false,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00
};
*/

// Preset Intensa (Muchos puntos, muy denso)
/*
const VANTA_CONFIG = {
    color: 0xff00ff,
    backgroundColor: 0x1a0033,
    points: 25,
    maxDistance: 30,
    spacing: 10,
    showDots: true,
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.00,
    minWidth: 200.00,
    scale: 1.00,
    scaleMobile: 1.00
};
*/

export default VANTA_CONFIG;
