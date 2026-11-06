
DROP DATABASE IF EXISTS cafeconecta;
CREATE DATABASE cafeconecta CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE cafeconecta;

CREATE TABLE perfil (
  Idperfil  INT(11)     NOT NULL AUTO_INCREMENT,
  descripc  VARCHAR(50) NOT NULL,
  estado    VARCHAR(20) NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (Idperfil),
  UNIQUE KEY uq_perfil_descripc (descripc),
  CONSTRAINT ck_perfil_estado CHECK (estado IN ('Activo', 'Inactivo'))
) ENGINE=InnoDB;

CREATE TABLE persona (
  Idpersona  INT(11)      NOT NULL AUTO_INCREMENT,
  nom1       VARCHAR(50)  NOT NULL,
  nom2       VARCHAR(50)  DEFAULT NULL,
  apell1     VARCHAR(50)  NOT NULL,
  apell2     VARCHAR(50)  DEFAULT NULL,
  direccion  VARCHAR(100) DEFAULT NULL,
  tele       VARCHAR(20)  DEFAULT NULL,
  movil      VARCHAR(20)  NOT NULL,
  correo     VARCHAR(100) NOT NULL,
  fecha_nac  DATE         DEFAULT NULL,
  estado     VARCHAR(20)  NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (Idpersona),
  UNIQUE KEY uq_persona_correo (correo),
  CONSTRAINT ck_persona_estado CHECK (estado IN ('Activo', 'Inactivo'))
) ENGINE=InnoDB;

CREATE TABLE usuario (
  Idusuario   INT(11)      NOT NULL AUTO_INCREMENT,
  nombreu     VARCHAR(50)  NOT NULL,
  contrasena  VARCHAR(255) NOT NULL,
  idperfil    INT(11)      NOT NULL,
  idpersona   INT(11)      NOT NULL,
  estado      VARCHAR(20)  NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (Idusuario),
  UNIQUE KEY uq_usuario_nombreu (nombreu),
  UNIQUE KEY uq_usuario_persona (idpersona),          -- relación 1 a 1 con persona
  KEY fk_usuario_perfil (idperfil),
  CONSTRAINT fk_usuario_perfil  FOREIGN KEY (idperfil)  REFERENCES perfil (Idperfil),
  CONSTRAINT fk_usuario_persona FOREIGN KEY (idpersona) REFERENCES persona (Idpersona),
  CONSTRAINT ck_usuario_estado CHECK (estado IN ('Activo', 'Inactivo'))
) ENGINE=InnoDB;


INSERT INTO perfil (Idperfil, descripc, estado) VALUES
  (1, 'Administrador', 'Activo'),
  (2, 'Persona',       'Activo');

-- IMPORTANTE: cambie el correo por uno real al que tenga acceso para probar
-- la recuperación de usuario y contraseña.
INSERT INTO persona (Idpersona, nom1, nom2, apell1, apell2, direccion, tele, movil, correo, fecha_nac, estado) VALUES
  (1, 'Carlos', NULL, 'Sanchez', NULL, 'Finca La Esperanza, Girón', NULL, '3001234567', 'carlos@cafeconecta.com', '1990-05-12', 'Activo');

INSERT INTO usuario (Idusuario, nombreu, contrasena, idperfil, idpersona, estado) VALUES
  (1, 'admin', 'admin123', 1, 1, 'Activo');
