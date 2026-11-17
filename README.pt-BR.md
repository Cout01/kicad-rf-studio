# kicad-rf-studio

*English version: [README.md](README.md).*

O kicad-rf-studio lê placas do KiCad e simula as partes de RF delas com o openEMS, um simulador eletromagnético no domínio do tempo (FDTD). É software livre, sob a GNU General Public License v3.0 ou posterior (veja `LICENSE`); a cópia do SmoothMeshLines do CSXCAD que ele inclui está sob a GNU Lesser General Public License v3.0 ou posterior (veja `COPYING.LESSER`).

Este é o guia em português. O [README em inglês](README.md) traz a saída real de cada comando e os tempos medidos em detalhe, e os registros de validação ficam em `docs/validation`.

## O que ele faz

Tudo parte da placa salva no KiCad. São três tipos de projeto, simulados no openEMS, e uma revisão rápida, sem simulação:

- **Cadeia de casamento:** traça a cadeia de RF entre dois pads, por exemplo do pino do rádio ao conector, simula o layout com cada componente da cadeia como uma porta e calcula o S da cadeia. Depois, o `retune` testa novos valores de componentes em segundos, sem simulação nova.
- **Antena:** simula a placa inteira numa caixa de ar com absorvedor (PML), do pino do rádio até a antena impressa: S11 na banda, carta de Smith e impedância de entrada. Com o `verify`, também a eficiência, a diretividade, o ganho e os cortes do diagrama de radiação.
- **Integridade de sinal:** mede uma linha ou um par diferencial, como o do USB: o TDR ao longo da rota contra a faixa de impedância da interface, o S de modo misto (Sdd21, Sdd11, Scc21 e Scd21), o skew e o crosstalk numa rede vizinha.
- **Revisão de EMC:** em segundos e sem rodar o openEMS, mede as redes marcadas (clocks, por exemplo) contra quatro regras práticas de geometria, R1 a R4, e calcula os modos de ressonância das cavidades entre planos.

**Os resultados são relativos.** Eles comparam variantes de uma mesma placa sob configurações idênticas e não preveem o desempenho medido em bancada. O `retune` instantâneo continua marcado como "relativo / what-if" enquanto não for validado contra a simulação completa de uma placa real; o `verify` confere os valores finais com uma simulação nova.

Há duas formas de usar, com o mesmo motor: a janela do programa (`kicad-rf-studio-gui`) e a linha de comando (`kicad-rf-studio`). Um botão no editor de PCI do KiCad (9.0.7 ou posterior, ou 10.x) abre a janela já com o que você selecionou na placa. A simulação roda no openEMS, em processos separados, nunca dentro do KiCad.

## Instalação

O kicad-rf-studio roda num ambiente virtual Python próprio, chamado `<venv>` abaixo. O pip instala nele o programa e as dependências Python, o Qt entre elas (cerca de 600 MB em disco); o openEMS 0.37 é instalado à parte. Enquanto o kicad-rf-studio não estiver no PyPI, `<source>` é o zip do código de uma release na página do projeto no GitHub ou um clone deste repositório.

### Windows

No PowerShell, no Windows 10 ou 11:

1. Instale o Python 3.14 de 64 bits para o seu usuário: pelo gerenciador de instalação do Python (`py install 3.14`), que não pede direitos de administrador, ou pelo python.org. As wheels do openEMS 0.37 para Windows pedem Python 3.13 ou 3.14.
2. Crie o venv em `%LOCALAPPDATA%\kicad-rf-studio\venv` e instale o kicad-rf-studio nele. `$venv` aponta para ele nos comandos abaixo; uma janela nova do PowerShell precisa da primeira linha de novo.

   ```
   $venv = "$env:LOCALAPPDATA\kicad-rf-studio\venv"
   py -3.14 -m venv $venv
   & "$venv\Scripts\python" -m pip install <source>
   ```

3. Descompacte o pacote oficial do openEMS 0.37 para Windows e passe a pasta dele, a que contém `openEMS.exe` e `python\`, ao `setup-openems`. Ele instala no venv, sem internet, as wheels do openEMS e do CSXCAD que vêm no pacote, e guarda o caminho da pasta.

   ```
   & "$venv\Scripts\kicad-rf-studio" setup-openems "<pasta do openEMS>"
   ```

4. Abra o KiCad uma vez antes, para ele criar a pasta da versão (ou indique a versão com `--kicad 9.0` ou `--kicad 10.0`). Instale o botão do KiCad, para o KiCad 9.0.7 ou posterior, ou 10.x. Ele grava na pasta de plugins de cada versão do KiCad e nunca altera as configurações do KiCad. Depois, no KiCad: Preferências › Plug-ins › Ativar a API do KiCad, e reinicie o KiCad. O botão aparece então na barra de ferramentas do editor de PCI.

   ```
   & "$venv\Scripts\kicad-rf-studio" install-kicad-plugin
   ```

5. Abra a janela com `& "$venv\Scripts\kicad-rf-studio-gui"`, ou pelo editor de PCI do KiCad: selecione os dois pads das pontas da cadeia; ou o footprint da antena (ou um pad dele) e o pino do rádio; ou uma trilha, arco ou via de uma linha de integridade de sinal. Depois pressione o botão do kicad-rf-studio. Sempre que atualizar o kicad-rf-studio, rode `install-kicad-plugin` de novo: a dica do botão, que diz o que ele aceita, é gravada nesse passo.

### Linux

No Debian 12, Ubuntu 24.04 ou Fedora (glibc 2.34 ou mais nova), com o Python do sistema (3.11 ou mais novo):

1. Clone o openEMS-Project oficial na v0.37.0, com os submódulos, e instale as dependências de compilação. É o único passo que pede direitos de administrador: o script pergunta e instala os pacotes da sua distribuição com sudo, o `python3-venv` entre eles no Debian e no Ubuntu.

   ```
   git clone --recursive --branch v0.37.0 https://github.com/thliebig/openEMS-Project.git
   cd openEMS-Project
   ./scripts/install_deps.sh --install --python
   ```

2. Crie o venv em `~/.local/share/kicad-rf-studio/venv`, ative-o e instale o kicad-rf-studio nele:

   ```
   python3 -m venv ~/.local/share/kicad-rf-studio/venv
   source ~/.local/share/kicad-rf-studio/venv/bin/activate
   pip install <source>
   ```

3. Com o venv ativo, compile o openEMS na pasta do openEMS-Project, sem sudo, para que os bindings Python dele fiquem no venv: `./update_openEMS.sh ~/.local/share/kicad-rf-studio/openEMS --python`. Deixe a interface gráfica ligada (sem `--disable-GUI`): ela compila o AppCSXCAD.
4. Abra o KiCad uma vez antes (ou indique a versão com `--kicad 9.0` ou `--kicad 10.0`). Com o venv ativo, instale o botão: `kicad-rf-studio install-kicad-plugin`. Depois, no KiCad: Preferências › Plug-ins › Ativar a API do KiCad, e reinicie o KiCad. O KiCad em Flatpak não consegue iniciar o botão: abra a placa pela janela do kicad-rf-studio.
5. Abra a janela com `kicad-rf-studio-gui`. Num desktop, o Qt precisa da biblioteca de cursor do xcb: `libxcb-cursor0` no Debian e no Ubuntu, `xcb-util-cursor` no Fedora.

### Depois de instalar

- **Moveu o venv?** Os programas `kicad-rf-studio` dele e o lançador do botão ainda apontam para o lugar antigo. Reinstale o kicad-rf-studio e rode `install-kicad-plugin` de novo, os dois pelo Python do venv no lugar novo: `& "<venv>\Scripts\python" -m pip install --force-reinstall --no-deps <source>` e depois `& "<venv>\Scripts\python" -m kicad_rf_studio install-kicad-plugin` (no Linux, `<venv>/bin/python` nos dois). Até lá o botão falha: o KiCad 10 mostra o erro do shell, e o KiCad 9 não mostra nada.
- **Remover o botão:** `& "$venv\Scripts\kicad-rf-studio" install-kicad-plugin --remove` (no Linux, com o venv ativo: `kicad-rf-studio install-kicad-plugin --remove`) apaga a pasta dele na pasta de plugins de cada versão do KiCad, e nada mais. Se o venv já não existir, apague à mão a pasta `kicad-rf-studio` de cada `Documents\KiCad\<versão>\plugins` (Windows) ou `~/.local/share/kicad/<versão>/plugins` (Linux).
- **Desinstalar:** remova o botão e apague o venv; no Linux, também a pasta do openEMS, `~/.local/share/kicad-rf-studio/openEMS`, e o clone do openEMS-Project. A pasta que contém o venv, `%LOCALAPPDATA%\kicad-rf-studio` ou `~/.local/share/kicad-rf-studio`, também guarda as configurações e as pastas das execuções para onde os resultados dos seus projetos apontam: apague-a só quando nenhum projeto precisar delas.
- **Idioma:** o kicad-rf-studio usa o idioma indicado por `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` ou `LANG`, quando um deles está definido; senão, português do Brasil quando o idioma de exibição do Windows é Português (Brasil); senão, inglês. Para usá-lo em inglês num Windows em português, rode `setx LANGUAGE en` uma vez e reinicie o KiCad; o git e outros programas que leem `LANGUAGE` também passam para inglês. No Linux, ponha `export LANGUAGE=en` no seu perfil.

## Tutoriais

Os quatro tutoriais usam placas sintéticas de `tests/fixtures`. Rode os comandos na raiz de um clone, ou do zip do código descompactado, com o venv da Instalação. No PowerShell, `<venv>\Scripts\kicad-rf-studio` é `& "$venv\Scripts\kicad-rf-studio"`; no Linux, com o venv ativo, digite só `kicad-rf-studio`.

Os tempos foram medidos no PC de desenvolvimento (Windows 11, 16 CPUs), no preset Normal, o padrão do `new`. O `cost` imprime a estimativa da sua máquina antes de cada execução, e nenhum tempo é prometido.

### Cadeia de casamento: `lpf915`

O `lpf915` é um filtro passa-baixas sintético de 915 MHz: um capacitor de bloqueio DC em série e um pi C-L-C de componentes 0402 numa GCPW de 50 Ω, sob uma blindagem.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o lpf915
<venv>\Scripts\kicad-rf-studio cost lpf915
<venv>\Scripts\kicad-rf-studio run lpf915
<venv>\Scripts\kicad-rf-studio retune lpf915 C2=4.7pF
<venv>\Scripts\kicad-rf-studio verify lpf915
```

- **`new`** lê a placa, traça a cadeia entre os pads U1.1 e J1.1 e grava o `project.json`, com a cadeia, os componentes, as portas e todos os valores padrão; você pode editá-lo. `--lid-height` é a altura da tampa da blindagem, em mm.
- **`cost`** imprime o Z0 e o εeff 2D dos trechos retos, roda a verificação de configuração do openEMS e estima o custo da execução: células, tempo no pior caso e RAM. Numa máquina ainda sem calibração, ele mede a velocidade dela uma vez; levou 40 s.
- **`run`** roda as verificações e um job por porta (P1, P2 e as portas dos componentes C1, L1, C2 e C3) sob a regra de parada, grava os resultados no `project.json` e escreve `layout.s6p`, `chain.s2p`, `summary.csv` e `summary.png` em `lpf915\results`. Os seis jobs levaram 5,5 h.
- **`retune`** grava valores novos e refaz os resultados a partir das ondas da última execução, sem simulação nova, em cerca de 2 s.
- **`verify`** roda mais uma vez com cada componente dentro da grade, no seu valor ideal, e compara com um retune nos mesmos valores. Na gate P0-B, com a configuração da época, levou 2,0 h.

O retune continua marcado "relativo / what-if" porque a validação contra uma placa real (gate P0-C) não foi feita. A gate P0-B reprovou, e nela o critério de consistência entre o `verify` e a co-simulação ficou fora: |ΔS21| em f0 de 0,1019 dB contra 0,1 dB, e |ΔS| máximo de 0,0926 contra 0,03. Leia o relatório (`docs/validation/2026-10-25-p0-b.md`) antes de tomar a comparação do `verify` como concordância.

### Antena: `ifa2g4_pi`

O `ifa2g4_pi` é uma placa sintética de 2,4 GHz com a antena F invertida `Texas_SWRA117D_2.4GHz_Left` do KiCad (da nota de aplicação SWRA117D da TI), alimentada pelo pad do rádio U1.1 através de um pi de componentes 0402: L1 em série, C2 e C3 em derivação. O `ifa2g4_pi_pour` é a mesma placa com um plano de terra dentro da área livre da antena.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi
<venv>\Scripts\kicad-rf-studio cost ifa2g4_pi
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi L1=0R C2=0.13pF C3=1pF
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi_pour.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi_pour L1=0R C2=0.13pF C3=1pF
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio compare ifa2g4_pi ifa2g4_pi_pour -o compare
```

- **`new --antenna`** acha o footprint da antena AE1 e o pad de alimentação dela, traça a cadeia desde o pino do rádio e grava um projeto de antena para a banda: `--antenna` substitui `--end`, e `--band F_LO:F_HI` substitui `--f0`. A placa inteira é simulada numa caixa de ar com absorvedor PML, e cada componente da cadeia é uma porta, para poder ser reajustado.
- **`run`** dá o S11 no pino do rádio para quaisquer valores dos componentes, sem campo distante, porque uma porta de componente não é o componente. Levou 1,1 h.
- **`retune`** fecha as portas dos componentes nos valores novos, sem simulação nova, em 2 s. `0R` troca um componente em série por um curto, e `open` remove um componente em derivação.
- **`verify`** roda um job com cada componente dentro da grade, no valor aplicado, e grava o campo distante: as eficiências de radiação e total, a diretividade, o ganho, o ganho realizado e os três cortes em f0. Levou 19 min.
- **`compare`** lê os resultados verificados dos dois projetos, que precisam ter as mesmas configurações, marca cada diferença como resolvida ou não e grava `compare.csv` e `compare.png` em `compare`.

Na janela, o Tipo Antena pede o footprint da antena, o pad de início e uma banda. A aba Resultados e ajuste mostra o S11 com a banda sombreada, a carta de Smith e, da execução que tem a rede, as eficiências e os cortes; a aba Comparação compara o projeto aberto com uma variante. O botão do KiCad já escolhe o tipo Antena quando o footprint da antena, ou um pad dele, está selecionado junto com o pino do rádio.

**O que estes resultados não dizem:**

- Todo resultado de antena traz a linha: "Relativo: estes resultados de antena comparam variantes de uma placa com configurações idênticas; eles não preveem o desempenho medido."
- A placa está sozinha no espaço livre: sem gabinete, mão, bateria ou cabo. A nota AN043 da TI mediu um desvio de 5 a 10 MHz só pela posição de um cabo.
- O cobre é um condutor perfeito, então a eficiência de radiação sai alta; os corpos dos componentes não existem no modelo.
- Uma diferença só é resolvida acima de 0,3 % de f0 para uma frequência e de 0,2 dB para uma eficiência ou um ganho, pelo menos três vezes o ruído medido do modelo (gate P3-D).
- O retune continua what-if: o `verify` confere a redução do layout com componentes ideais, não os componentes reais do fabricante.
- Antenas chip e módulos são recusados; a cadeia de casamento até o pad deles ainda roda como no tutorial da cadeia.

### Integridade de sinal: `usb2_hs`

O `usb2_hs` é uma placa sintética de quatro camadas com USB 2.0 high-speed: um conector micro-B J1, os pads de um array de ESD U2 no par, um resistor série de 22 Ω 0402 em cada perna (R1 e R2) e um QFN parecido com um MCU (U1) na outra ponta, com uma rede vizinha, AUX, correndo ao lado de parte da rota entre os pontos de teste TP1 e TP2. O `usb2_hs_gap` é a mesma placa com uma fenda no plano sob o par.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs
<venv>\Scripts\kicad-rf-studio cost usb2_hs
<venv>\Scripts\kicad-rf-studio run usb2_hs
<venv>\Scripts\kicad-rf-studio retune usb2_hs R1=24 R2=24
<venv>\Scripts\kicad-rf-studio verify usb2_hs
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs_gap.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs_gap
<venv>\Scripts\kicad-rf-studio run usb2_hs_gap
<venv>\Scripts\kicad-rf-studio retune usb2_hs_gap R1=24 R2=24
<venv>\Scripts\kicad-rf-studio verify usb2_hs_gap
<venv>\Scripts\kicad-rf-studio compare usb2_hs usb2_hs_gap -o compare
```

- **`new --interface`** traça a linha medida do pino J1.3 do conector, passando por R1, até o pino U1.3 do MCU, pega o par pela regra de pares do KiCad (`--pair`) e a AUX entre TP1.1 e TP2.1 como vítima, e grava um projeto de integridade de sinal para a interface `usb2-hs`: 90 Ω diferencial ± 10 %, borda de 500 ps e marcador em 240 MHz, simulado até 10 GHz. R1 e R2 viram portas, para poderem ser reajustados.
- **`cost`** lista primeiro a tabela 2D, com a impedância de cada trecho reto contra a faixa alvo, em segundos e antes de qualquer execução; depois as células, as execuções e o pior caso.
- **`run`** roda um job por porta (as quatro pontas do par, as duas da vítima e R1 e R2) e dá o TDR ao longo da rota, o S de modo misto, o skew e o crosstalk na AUX, para quaisquer valores de R1 e R2. Levou 39 min.
- **`retune`** fecha as portas em valores novos, sem simulação nova, em 7 s. O **`verify`** roda com R1 e R2 dentro da grade, nos valores aplicados, e compara com o retune; levou 30 min.
- **`compare`** marca cada diferença como resolvida ou não, pelos limiares que a gate P4-E mediu: 2,2 Ω num nível de TDR, 0,05 dB em Sdd21 ou S21, 0,5 dB em Sdd11, S11, NEXT e FEXT (quando o maior dos dois níveis fica acima de −50 dB) e em Scd21 (acima de −37,7 dB), e 1 ps no skew.

Na janela, o Tipo Integridade de sinal pede os pads de início e de fim, a interface, o par e até duas vítimas. A aba Custo lista a tabela 2D antes da estimativa, e a aba Resultados e ajuste mostra o TDR com a faixa alvo, o S de modo misto e o crosstalk, e reajusta R1 e R2 com valores da série E24. O botão do KiCad já preenche o tipo, o par e uma interface compatível a partir de uma trilha, arco ou via selecionados.

**O que estes resultados não dizem:**

- Todo resultado traz a linha: "Relativo: estes resultados de integridade de sinal comparam variantes de uma placa com configurações idênticas; eles não preveem o desempenho medido."
- Um nível de TDR sobre um trecho mais curto que dois comprimentos de resolução não é a impedância desse trecho; a tabela 2D dá a de um trecho reto.
- Cobre em 45° ou em arcos vira degraus na malha e só gera um aviso: a gate P4-B mediu um par em 45° 2,27 % (90 Ω) e 5,35 % (100 Ω) fora do gêmeo alinhado aos eixos.
- O dielétrico é sem perdas por padrão. `"dielectric": "debye"` no `project.json` inclui a perda, mas esta placa rodaria cerca de 33 vezes mais devagar (gate P4-D).
- As ressonâncias dos planos ficam soando num modelo sem perdas e dependem do recorte da placa, então as frequências e as profundidades delas não são previsões.
- O cobre é um condutor perfeito, e encapsulamentos, dies e o corpo do conector não existem no modelo. O retune continua what-if.

### Revisão de EMC: `emc_review` e `lpf915`

O `emc_review` é uma placa sintética de quatro camadas feita para a revisão: 50 × 50 mm, GND em In1.Cu e +3V3 em In2.Cu, com quatro redes de clock e uma blindagem, cada uma um caso de uma regra. O `review` lê a placa como foi salva, mede as redes marcadas e as blindagens contra as regras R1 a R4 e calcula os modos das cavidades entre planos, em segundos e sem rodar o openEMS. Ele grava `review.csv` (uma linha por achado), `review.json` (as configurações, os achados com os IDs do KiCad e as cavidades) e `review.png` na pasta indicada por `-o`, e termina com código 0, com ou sem achados.

```
<venv>\Scripts\kicad-rf-studio review tests/fixtures/emc_review.kicad_pcb -o review
<venv>\Scripts\kicad-rf-studio review tests/fixtures/lpf915.kicad_pcb --net "RF_*" --f0 915MHz -o review
```

- **Redes marcadas:** sem `--net`, os padrões de nome marcam as redes das famílias CLK, SCK, XTAL, SW, SPI, I2S e USB, a menos que a última palavra do nome seja CTRL, NSS, DIO, BUSY, RST, IRQ, EN ou CS: CLK_GEN é marcada, SPI_CS não. `--net` dá nomes ou padrões no lugar deles, e `--project` acrescenta a cadeia ou as linhas de um projeto. Cada rede marcada traz junto as redes ligadas a ela por componentes em série de dois pads e o seu par diferencial. Redes de terra e de alimentação nunca são marcadas.
- **f_max e L:** o `--f-max`, quando dado; senão, 5 vezes a portadora (o `--f0` ou a de um projeto), no máximo 6 GHz; senão, o f_max de um projeto de integridade de sinal, no máximo 6 GHz; senão, 5 GHz. L é λ/20 no dielétrico em f_max.
- **R1:** trechos de uma trilha marcada sem plano de referência embaixo (vazios ou fendas), a partir de 1 mm.
- **R2:** numa via onde a referência muda, pede um capacitor entre as duas redes a até max(L, 2 mm), ou uma via de costura quando é a mesma rede. É só informativa.
- **R3:** trilha marcada a menos de k·h da borda da placa, com k = 2 (`--edge-k`).
- **R4:** vãos entre as vias de GND ao longo do quadro de cada blindagem, contra L; `--edge-fence` inclui a cerca da borda da placa.
- **Cavidades:** cada par de planos com 20 mm² ou mais. Os modos até f_max são resolvidos em 2D numa grade de 0,25 mm, e um modo é marcado quando fica a ±5 % de um harmônico da portadora ou de um clock dado com `--clock`.

Na janela, a aba Revisão pede a placa, as Redes marcadas e o f0, e o botão Revisar a placa roda a revisão com o projeto aberto, se houver. Selecionar no KiCad seleciona no editor de PCI os itens dos achados escolhidos na tabela: ele precisa antes de um clique no botão do kicad-rf-studio no KiCad, recusa quando o KiCad está com outra placa aberta e nunca dá zoom. Simular isto, num achado R1, R2 ou R3, prepara um projeto de integridade de sinal na rede daquele achado.

**O que estes resultados não dizem:**

- Toda revisão traz a linha: "Regras de geometria, não um veredito de conformidade: cada achado mede a placa como foi salva contra uma regra prática publicada, citada com a sua fonte; nada aqui prevê aprovação ou reprovação."
- Os limiares foram ajustados em apenas três placas públicas, por um só avaliador; rodar a revisão nas suas próprias placas é o que os calibra.
- A R2 é só informativa, e a R4 compara um vão com λ/20, sem nunca imprimir uma atenuação.
- As áreas de keep-out da placa não entram na importação, então a revisão só vê os preenchimentos que elas moldam.
- Os modos das cavidades vêm de um modelo sem perdas, que diz onde uma ressonância pode ficar e nunca a altura dela, sem os capacitores de desacoplamento e sem o efeito de borda, então as frequências saem um pouco altas (a gate E-E mediu 1,0 % num par de 50 × 30 mm com d de 0,8 mm).

## Desenvolvimento

1. Crie um ambiente virtual: `python -m venv .venv`
2. Ative-o: `.venv\Scripts\activate` no Windows, `source .venv/bin/activate` nos outros sistemas.
3. Instale o pacote em modo editável, com os extras de desenvolvimento: `python -m pip install -e .[dev]`
4. Dê o openEMS ao venv como na Instalação (no Windows, `kicad-rf-studio setup-openems <pasta do openEMS>`, com `CSXCAD_INSTALL_PATH` apontando para essa pasta: os testes importam o openEMS neste Python, que a usa para achar as DLLs dele). Sem isso, os testes marcados `openems` são pulados.
5. Rode os testes: `python -m pytest -q`. Eles rodam em inglês, qualquer que seja o idioma do sistema, e `KRS_TEST_LANGUAGE=pt_BR` roda `tests/test_gui.py` em português.
6. Antes de uma release, rode `python tools/release_check.py`. As execuções reais pela janela estão descritas no README em inglês.
7. Depois de mudar uma mensagem em `src/kicad_rf_studio/core/messages.py`, rode `python tools/catalog.py`, traduza cada entrada de `po/pt_BR.po` com msgstr vazio e rode-o de novo: os testes recusam um catálogo incompleto ou não compilado.

## Contribuindo

Configure a trava de privacidade local antes de fazer commit ou push. Ela recusa nomes privados, caminhos absolutos de unidade e de pasta pessoal, compartilhamentos de rede e endereços de e-mail. A CI repete só as verificações genéricas.

1. Escreva as palavras que nunca podem sair da sua máquina num arquivo de texto UTF-8 fora do repositório, uma por linha. Linhas em branco e linhas que começam com `#` são ignoradas, e a comparação ignora maiúsculas e minúsculas.
2. Aponte `KRS_PRIVATE_LIST` para esse arquivo. No PowerShell: `$env:KRS_PRIVATE_LIST = "<caminho do arquivo>"`. Num shell POSIX: `export KRS_PRIVATE_LIST=<caminho do arquivo>`.
3. Ative os hooks: `git config core.hooksPath .githooks`

Os hooks rodam `tools/privacy_gate.py` com o Python do seu `PATH`, que só precisa da biblioteca padrão. Sem uma lista válida, eles recusam o commit ou o push. `python tools/privacy_gate.py --all` varre o histórico inteiro à mão. Um achado aparece como `<onde>:<linha>: <regra>`, em que `deny#N` é a N-ésima entrada da sua lista e `generic:...` é uma das regras embutidas. A trava nunca imprime o texto encontrado.
