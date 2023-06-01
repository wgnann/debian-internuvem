# Debian Internuvem

Configurações adicionais baseadas na [imagem oficial do Debian para nuvem](https://cloud.debian.org/images/cloud/).

Implementa a classe `INTERNUVEM`, criando um modelo da imagem compatível com a internuvem.usp.br.


## Como usar

Build testado no Debian 11. Deve funcionar no 12.

```bash
apt install ca-certificates debsums dosfstools fai-server fai-setup-storage fdisk make python3 python3-libcloud python3-marshmallow python3-pytest python3-yaml qemu-utils udev

```

Depois basta:

1 - Clonar o repositório.

2 - Baixar o pacote `xe-guest-utilities` para o diretório `localdebs` obtido aqui:

https://github.com/xenserver/xe-guest-utilities

Testamos esta versão:

https://github.com/xenserver/xe-guest-utilities/releases/download/v7.20.2/xe-guest-utilities_7.20.2-1_amd64.deb

Basta colocar o `.deb` dentro do diretório que o montador entende.

3 - Compilar a imagem, gerando o arquivo `image_bookworm_internuvem_amd64.raw`:
```bash
make image_bookworm_internuvem_amd64
```

4 - Converter a imagem para VHD:
```bash
qemu-img convert -f raw -O vpc image_bookworm_internuvem_amd64.raw debian12.vhd
```

5 - Adicionar na nuvem. Basta fazer upload para algum local e adicionar via URL. Marcamos:
  * isextractable;
  * passwordenabled;
  * requireshvm.

O ostype é `Other Linux amd64`.

Recomendamos fortemente ler o `README` do [projeto oficial](https://salsa.debian.org/cloud-team/debian-cloud-images/-/blob/master/README.md).

## O que mudou em relação ao original?
  - Trocamos o `build-type` para `official`;
  - Adicionamos `internuvem` como `vendor`;
  - Adicionamos o CloudStack como provider à classe `INTERNUVEM`;
  - Adicionamos o pacote `xe-guest-utilities` à classe `INTERNUVEM`.
