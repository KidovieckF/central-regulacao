CREATE TABLE IF NOT EXISTS unidades_saude (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    codigo VARCHAR(50),
    telefone VARCHAR(20),
    endereco VARCHAR(255),
    ativo TINYINT(1) DEFAULT 1
);

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
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (unidade_id) REFERENCES unidades_saude(id)
);

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
);

CREATE TABLE IF NOT EXISTS exames (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paciente_id INT NOT NULL,
    exame_id INT NOT NULL,
    unidade_id INT NOT NULL,
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
    FOREIGN KEY (unidade_id) REFERENCES unidades_saude(id),
    FOREIGN KEY (usuario_criacao) REFERENCES usuarios(id),
    FOREIGN KEY (usuario_atualizacao) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS historico_pedidos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pedido_id INT NOT NULL,
    status VARCHAR(64) NOT NULL,
    descricao TEXT,
    criado_por INT NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
    FOREIGN KEY (criado_por) REFERENCES usuarios(id)
);

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
);

CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (user_id) REFERENCES usuarios(id)  -- Referência à tabela de usuários existente
);

CREATE TABLE IF NOT EXISTS attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size INT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id)  -- Referência à tabela de mensagens
);

CREATE TABLE IF NOT EXISTS conversation_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (user_id) REFERENCES usuarios(id)
);
