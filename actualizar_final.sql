-- =====================================================================
-- Café Conecta · Actualización de la base del Parcial II al Final
-- Importe este archivo UNA SOLA VEZ sobre la base 'cafeconecta' que ya
-- tiene del Parcial II. No borra ninguno de sus datos.
-- =====================================================================

SET NAMES utf8mb4;
USE cafeconecta;

-- ---------------------------------------------------------------------
-- FINAL · Listas de empaques y medios de pago
-- ---------------------------------------------------------------------
CREATE TABLE empaque (
  idempaque    INT(11)     NOT NULL AUTO_INCREMENT,
  descripcion  VARCHAR(60) NOT NULL,
  estado       VARCHAR(20) NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (idempaque),
  UNIQUE KEY uq_empaque_descripcion (descripcion)
) ENGINE=InnoDB;

CREATE TABLE medio_pago (
  idmedio      INT(11)     NOT NULL AUTO_INCREMENT,
  descripcion  VARCHAR(40) NOT NULL,
  estado       VARCHAR(20) NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (idmedio),
  UNIQUE KEY uq_medio_descripcion (descripcion)
) ENGINE=InnoDB;

INSERT INTO empaque (descripcion) VALUES
  ('Saco de fique'), ('Saco de polipropileno'), ('Saco de yute'), ('Bolsa de válvula');

INSERT INTO medio_pago (descripcion) VALUES
  ('Transferencia bancaria'), ('Nequi'), ('Daviplata'), ('Cheque'), ('Efectivo');

-- ---------------------------------------------------------------------
-- HU-06 · Inventario de lotes de café
-- peso: kg de cada empaque · cantidad: número de empaques · precio: por kg
-- La cantidad comprometida y la disponible se calculan con los negocios.
-- ---------------------------------------------------------------------
CREATE TABLE lote (
  codigoc         VARCHAR(15)   NOT NULL,
  descripcion     VARCHAR(200)  NOT NULL,
  imagen          MEDIUMBLOB    NOT NULL,
  imagen_tipo     VARCHAR(10)   NOT NULL,
  peso            DECIMAL(8,2)  NOT NULL,
  cantidad        INT(11)       NOT NULL,
  precio          DECIMAL(12,2) NOT NULL,
  codigof         VARCHAR(15)   NOT NULL,
  codigotv        VARCHAR(10)   NOT NULL,
  idempaque       INT(11)       NOT NULL,
  fecha_registro  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado          VARCHAR(20)   NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (codigoc),
  KEY fk_lote_finca (codigof),
  KEY fk_lote_variedad (codigotv),
  KEY fk_lote_empaque (idempaque),
  CONSTRAINT fk_lote_finca FOREIGN KEY (codigof) REFERENCES finca (codigof),
  CONSTRAINT fk_lote_variedad FOREIGN KEY (codigotv) REFERENCES variedad (codigotv),
  CONSTRAINT fk_lote_empaque FOREIGN KEY (idempaque) REFERENCES empaque (idempaque),
  CONSTRAINT ck_lote_peso CHECK (peso > 0),
  CONSTRAINT ck_lote_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_lote_precio CHECK (precio > 0),
  CONSTRAINT ck_lote_estado CHECK (estado IN ('Activo', 'Inactivo'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- HU-07 · Negocios (emparejamiento comercial) con su detalle
-- estado_negocio: Propuesto, Aceptado, Rechazado, En entrega, Completado, Cancelado
-- estado: Activo o Anulado (borrado lógico)
-- ---------------------------------------------------------------------
CREATE TABLE negocio (
  idnegocio       INT(11)       NOT NULL AUTO_INCREMENT,
  codigoe         VARCHAR(20)   NOT NULL,
  fecha_hora      DATETIME      NOT NULL,
  descripcion     VARCHAR(250)  DEFAULT NULL,
  idmedio         INT(11)       NOT NULL,
  valor_total     DECIMAL(14,2) NOT NULL DEFAULT 0,
  estado_negocio  VARCHAR(20)   NOT NULL DEFAULT 'Propuesto',
  documento       VARCHAR(12)   NOT NULL,
  nit             VARCHAR(12)   NOT NULL,
  idusuario       INT(11)       NOT NULL,
  motivo_rechazo  VARCHAR(250)  DEFAULT NULL,
  fecha_respuesta DATETIME      DEFAULT NULL,
  token           VARCHAR(40)   NOT NULL,
  estado          VARCHAR(20)   NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (idnegocio),
  UNIQUE KEY uq_negocio_codigoe (codigoe),
  UNIQUE KEY uq_negocio_token (token),
  KEY fk_negocio_productor (documento),
  KEY fk_negocio_cooperativa (nit),
  CONSTRAINT fk_negocio_medio FOREIGN KEY (idmedio) REFERENCES medio_pago (idmedio),
  CONSTRAINT fk_negocio_productor FOREIGN KEY (documento) REFERENCES productor (documento),
  CONSTRAINT fk_negocio_cooperativa FOREIGN KEY (nit) REFERENCES cooperativa (nit),
  CONSTRAINT fk_negocio_usuario FOREIGN KEY (idusuario) REFERENCES usuario (Idusuario),
  CONSTRAINT ck_negocio_estado_negocio CHECK (estado_negocio IN
    ('Propuesto', 'Aceptado', 'Rechazado', 'En entrega', 'Completado', 'Cancelado')),
  CONSTRAINT ck_negocio_estado CHECK (estado IN ('Activo', 'Anulado'))
) ENGINE=InnoDB;

CREATE TABLE detalle_negocio (
  iddetalle  INT(11)       NOT NULL AUTO_INCREMENT,
  idnegocio  INT(11)       NOT NULL,
  codigoc    VARCHAR(15)   NOT NULL,
  cantidad   INT(11)       NOT NULL,
  peso       DECIMAL(8,2)  NOT NULL,
  precio_kg  DECIMAL(12,2) NOT NULL,
  subtotal   DECIMAL(14,2) NOT NULL,
  PRIMARY KEY (iddetalle),
  UNIQUE KEY uq_detalle_lote (idnegocio, codigoc),
  KEY fk_detalle_lote (codigoc),
  CONSTRAINT fk_detalle_negocio FOREIGN KEY (idnegocio) REFERENCES negocio (idnegocio),
  CONSTRAINT fk_detalle_lote FOREIGN KEY (codigoc) REFERENCES lote (codigoc),
  CONSTRAINT ck_detalle_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_detalle_precio CHECK (precio_kg > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- HU-08 y HU-09 · Entregas y confirmación de recibido
-- estado_entrega: Programada, En tránsito, Recibida, Recibida con novedad, Cancelada
-- ---------------------------------------------------------------------
CREATE TABLE entrega (
  code                VARCHAR(20)   NOT NULL,
  iddetalle           INT(11)       NOT NULL,
  fecha               DATE          NOT NULL,
  hora                TIME          NOT NULL,
  cantidad            INT(11)       NOT NULL,
  descripcion         VARCHAR(200)  DEFAULT NULL,
  lugar               VARCHAR(150)  NOT NULL,
  estado_entrega      VARCHAR(25)   NOT NULL DEFAULT 'Programada',
  estado              VARCHAR(20)   NOT NULL DEFAULT 'Activo',
  fecha_registro      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  aviso_llegada       DATETIME      DEFAULT NULL,
  cantidad_recibida   INT(11)       DEFAULT NULL,
  novedad             VARCHAR(250)  DEFAULT NULL,
  fecha_confirmacion  DATETIME      DEFAULT NULL,
  idusuario_confirma  INT(11)       DEFAULT NULL,
  token               VARCHAR(40)   NOT NULL,
  PRIMARY KEY (code),
  UNIQUE KEY uq_entrega_token (token),
  KEY fk_entrega_detalle (iddetalle),
  CONSTRAINT fk_entrega_detalle FOREIGN KEY (iddetalle) REFERENCES detalle_negocio (iddetalle),
  CONSTRAINT fk_entrega_usuario FOREIGN KEY (idusuario_confirma) REFERENCES usuario (Idusuario),
  CONSTRAINT ck_entrega_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_entrega_estado_entrega CHECK (estado_entrega IN
    ('Programada', 'En tránsito', 'Recibida', 'Recibida con novedad', 'Cancelada')),
  CONSTRAINT ck_entrega_estado CHECK (estado IN ('Activo', 'Anulado'))
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Bitácora de mensajes de WhatsApp (cada mensaje enviado con su resultado)
-- ---------------------------------------------------------------------
CREATE TABLE mensaje (
  idmensaje     INT(11)      NOT NULL AUTO_INCREMENT,
  fecha_hora    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  telefono      VARCHAR(15)  NOT NULL,
  destinatario  VARCHAR(150) NOT NULL,
  tipo          VARCHAR(40)  NOT NULL,
  referencia    VARCHAR(40)  DEFAULT NULL,
  texto         TEXT         NOT NULL,
  medio         VARCHAR(20)  NOT NULL,
  resultado     VARCHAR(20)  NOT NULL,
  detalle       VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (idmensaje)
) ENGINE=InnoDB;
