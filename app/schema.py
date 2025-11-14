SCHEMA_STATEMENTS = [
    # -------------------------------------------------------------------------
    # Tabelas principais do sistema
    # -------------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unidades_saude (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        codigo VARCHAR(50),
        telefone VARCHAR(20),
        endereco VARCHAR(255),
        ativo TINYINT(1) DEFAULT 1
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        cpf CHAR(11) NOT NULL UNIQUE,
        senha_hash VARCHAR(255) NOT NULL,
        role ENUM(
            'admin',
            'recepcao',
            'malote',
            'medico_regulador',
            'agendador_municipal',
            'agendador_estadual'
        ) NOT NULL,
        unidade_id INT NULL,
        ativo TINYINT(1) DEFAULT 1,
        is_online BOOLEAN DEFAULT FALSE,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (unidade_id) REFERENCES unidades_saude(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS pacientes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        cpf CHAR(11) NOT NULL UNIQUE,
        data_nascimento DATE,
        telefone_principal VARCHAR(20),
        telefone_secundario VARCHAR(20),
        email VARCHAR(120),
        cartao_sus VARCHAR(20),
        endereco TEXT,
        unidade_id INT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (unidade_id) REFERENCES unidades_saude(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS exames (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        descricao TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS consultas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        nome VARCHAR(150) NOT NULL,
        especialidade VARCHAR(150) NOT NULL,
        descricao TEXT,
        ativo TINYINT(1) DEFAULT 1,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS pedidos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        paciente_id INT NOT NULL,
        exame_id INT NULL,
        consulta_id INT NULL,
        unidade_id INT NOT NULL,
        tipo_solicitacao ENUM('exame', 'consulta') DEFAULT 'exame',
        status VARCHAR(64) NOT NULL,
        tipo_regulacao ENUM('municipal', 'estadual') NULL,
        prioridade ENUM('P1', 'P2') NULL,
        data_solicitacao DATETIME DEFAULT CURRENT_TIMESTAMP,
        data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        usuario_criacao INT NOT NULL,
        usuario_atualizacao INT NOT NULL,
        motivo_cancelamento TEXT,
        motivo_devolucao TEXT,
        pendente_recepcao TINYINT(1) DEFAULT 0,
        anexos JSON NULL,
        data_exame DATE,
        horario_exame TIME,
        local_exame VARCHAR(255),
        observacoes TEXT,
        tentativas_contato INT DEFAULT 0,
        FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
        FOREIGN KEY (exame_id) REFERENCES exames(id),
        FOREIGN KEY (consulta_id) REFERENCES consultas(id),
        FOREIGN KEY (unidade_id) REFERENCES unidades_saude(id),
        FOREIGN KEY (usuario_criacao) REFERENCES usuarios(id),
        FOREIGN KEY (usuario_atualizacao) REFERENCES usuarios(id),
        CONSTRAINT chk_exame_ou_consulta CHECK (
            (exame_id IS NOT NULL AND consulta_id IS NULL) OR 
            (exame_id IS NULL AND consulta_id IS NOT NULL)
        )
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS historico_pedidos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pedido_id INT NOT NULL,
        status VARCHAR(64) NOT NULL,
        descricao TEXT,
        criado_por INT NOT NULL,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
        FOREIGN KEY (criado_por) REFERENCES usuarios(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS tentativas_contato (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pedido_id INT NOT NULL,
        tentativa_numero INT NOT NULL,
        resultado ENUM('contato_sucesso', 'sem_contato', 'recado', 'outra') NOT NULL,
        resumo TEXT,
        data_tentativa DATETIME DEFAULT CURRENT_TIMESTAMP,
        usuario_id INT NOT NULL,
        FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # -------------------------------------------------------------------------
    # Módulo de CHAT
    # -------------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        room VARCHAR(100) NOT NULL,
        name VARCHAR(200),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        conversation_id INT NOT NULL,
        user_id INT NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX (conversation_id),
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS attachments (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        message_id BIGINT NOT NULL,
        original_filename VARCHAR(512) NOT NULL,
        stored_filename VARCHAR(512) NOT NULL,
        mime_type VARCHAR(255),
        size INT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX (message_id),
        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_participants (
        id INT AUTO_INCREMENT PRIMARY KEY,
        conversation_id INT NOT NULL,
        user_id INT NOT NULL,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        UNIQUE KEY uq_conversation_user (conversation_id, user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
]